from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
import logging

_logger = logging.getLogger(__name__)

class DepartmentItemRequest(models.Model):
    _name = 'department.item.request'
    _description = 'Department Item Request'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, default=lambda self: 'New')
    requested_by_user = fields.Many2one('res.users', string='Requested By (User)', default=lambda self: self.env.uid, readonly=True)
    requested_date = fields.Datetime(string='Requested On', default=fields.Datetime.now, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Requested For', required=True)
    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id', store=True)
    line_ids = fields.One2many('department.item.request.line', 'request_id', string='Requested Lines', copy=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    picking_id = fields.Many2one('stock.picking', string='Related Picking', readonly=True)
    issued_by_user_id = fields.Many2one('res.users', string='Issued By', readonly=True)
    note = fields.Text(string='Notes')

    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('department.item.request') or 'REQ/0000'
        rec = super().create(vals)
        rec.message_post(body=_('Request %s created') % rec.name)
        return rec

    def _is_department_head(self, user):
        if not self.department_id:
            return False
        manager = self.department_id.manager_id
        return bool(manager and manager.user_id and manager.user_id.id == user.id)

    @api.constrains('employee_id')
    def _check_employee_department_on_create_or_change(self):
        for rec in self:
            if not rec.employee_id:
                continue
            user_employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            if not user_employee:
                raise UserError(_('You must be an employee linked to a user to create or modify requests.'))

            allowed_dept_ids = self.env['hr.department'].search([('id', 'child_of', user_employee.department_id.id)]).ids
            if rec.employee_id.department_id.id not in allowed_dept_ids and not self.env.user.has_group('base.group_system'):
                raise UserError(_('You can only create requests for employees in your department or sub-departments.'))

    def write(self, vals):
        blocking = self.filtered(lambda r: r.state in ('approved', 'done'))
        if blocking:
            raise UserError(_('This request has already been approved or completed and cannot be edited.'))
        return super().write(vals)

    def unlink(self):
        blocking = self.filtered(lambda r: r.state in ('approved', 'done'))
        if blocking:
            raise UserError(_('Cannot delete requests that are approved or done.'))
        return super().unlink()

    def _prepare_picking(self, rec):
        rec.department_id.ensure_stock_location()
        dest = rec.department_id.stock_location_id
        if not dest:
            raise UserError(_('Destination location for department not found. Contact admin.'))

        warehouse = self.env['stock.warehouse'].search([('lot_stock_id','=',dest.id)], limit=1)
        if not warehouse:
            raise UserError(_('No warehouse linked to department location %s') % dest.name)

        picking_type = warehouse.int_type_id
        if not picking_type:
            raise UserError(_('No internal picking type for warehouse %s') % warehouse.name)

        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': dest.id,
            'origin': rec.name,
            'note': rec.note or False,
            'move_type': 'direct',
        }
        return picking_vals, dest

    def _prepare_moves(self, rec, picking):
        moves = []
        for line in rec.line_ids:
            if not line.product_id:
                raise UserError(_('Request line has no product.'))
            product = line.product_id
            free_qty = product.with_context(location=picking.location_id.id, compute_qty=True, virtual_available=True).qty_available
            if free_qty < line.quantity:
                raise UserError(_('Not enough stock for %s. Available: %s') % (product.display_name, free_qty))
            moves.append({
                'name': product.display_name,
                'product_id': product.id,
                'product_uom_qty': line.quantity,
                'product_uom': product.uom_id.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'department_request_line_id': line.id,
            })
        return moves

    def action_submit(self):
        for rec in self:
            user = self.env.user
            if not user.has_group('base.group_system') and not rec._is_department_head(user):
                raise AccessError(_('Only the department head may submit this request.'))
            if rec.picking_id:
                raise UserError(_('This request already has a picking: %s') % (rec.picking_id.display_name or rec.picking_id.name))

            self.env.cr.savepoint()
            picking_vals, dest = rec._prepare_picking(rec)
            picking = self.env['stock.picking'].create(picking_vals)
            try:
                moves = rec._prepare_moves(rec, picking)
                if moves:
                    self.env['stock.move'].create([{
                        **m,
                        'picking_id': picking.id
                    } for m in moves])
                picking._action_confirm()
                picking.action_assign()
            except Exception as e:
                picking.unlink()
                raise UserError(_('Could not reserve stock for this request: %s') % e)

            rec.picking_id = picking.id
            rec.state = 'requested'
            rec.message_post(body=_('Request submitted and stock reserved (picking %s)') % picking.name)

    def action_approve(self):
        for rec in self:
            rec.state = 'approved'
            rec.message_post(body=_('Request approved by %s') % self.env.user.display_name)

    def action_done(self):
        for rec in self:
            if rec.picking_id and rec.picking_id.state != 'done':
                raise UserError(_('Please validate the related transfer before marking request as done.'))
            rec.state = 'done'
            rec.issued_by_user_id = self.env.uid
            rec.message_post(body=_('Request marked done by %s') % self.env.user.display_name)

    def action_cancel(self):
        for rec in self:
            if rec.picking_id:
                try:
                    rec.picking_id.action_cancel()
                except Exception as e:
                    _logger.warning('Failed to cancel picking %s: %s', rec.picking_id.name, e)
            rec.state = 'cancelled'
            rec.message_post(body=_('Request cancelled by %s') % self.env.user.display_name)
