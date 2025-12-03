from odoo import models, fields, api, exceptions, _
import traceback


class EmployeeItemRequest(models.Model):
    _name = 'employee.item.request'
    _description = 'Employee Item Request'
    _order = 'id desc'

    name = fields.Char(string='Request Reference', default='New', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom_qty = fields.Float(string='Quantity', required=True, default=1.0)

    employee_id = fields.Many2one('hr.employee', string='Requested For', required=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True, string='Department')

    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user.id, readonly=True)
    requested_date = fields.Datetime(string='Requested Date', default=fields.Datetime.now, readonly=True)

    picking_id = fields.Many2one('stock.picking', string='Related Picking', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], default='draft', string='Status')

    note = fields.Text(string='Notes')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('employee.item.request') or 'REQ/0000'
        if 'company_id' not in vals:
            vals['company_id'] = self.env.company.id
        return super(EmployeeItemRequest, self).create(vals)

    def action_request(self):
        for rec in self:
            rec.state = 'requested'
        return True

    def _select_picking_type_for_location(self, location):
        """
        Choose internal picking type whose warehouse includes the given location as an ancestor.
        Fallback: first internal picking type in the DB.
        """
        if not location:
            return self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)

        Warehouse = self.env['stock.warehouse']
        candidate_wh = Warehouse.search([], limit=1)
        whs = Warehouse.search([])
        for wh in whs:
            lot_loc = wh.lot_stock_id or wh.view_location_id
            if lot_loc:
                if location.id == lot_loc.id or location in lot_loc.child_ids:
                    return wh.int_type_id or self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)

        return self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)

    def action_approve(self):
        if not (self.env.user.has_group('stock.group_stock_user') or self.env.user.has_group('base.group_system')):
            raise exceptions.AccessError(_('You are not allowed to approve requests.'))

        StockMove = self.env['stock.move']
        try:
            source = self.env.ref('stock.stock_location_stock')
        except Exception:
            source = False
        try:
            dest = self.env.ref('employee_item_request.loc_issued_items')
        except Exception:
            dest = False

        if not source or not dest:
            raise exceptions.UserError(_('Source or destination location not configured.'))

        for rec in self:
            if rec.state != 'requested':
                raise exceptions.UserError(_('Only requests in Requested state can be approved.'))

            available = rec.product_id.with_context(location=source.id).qty_available
            if available < rec.product_uom_qty:
                raise exceptions.UserError(
                    _('Not enough stock for %s. Available: %s, Requested: %s') %
                    (rec.product_id.display_name, available, rec.product_uom_qty)
                )

            picking_type = self._select_picking_type_for_location(source)
            if not picking_type:
                raise exceptions.UserError(_('No internal picking type found. Configure a warehouse with internal transfers.'))

            picking_vals = {
                'picking_type_id': picking_type.id,
                'location_id': source.id,
                'location_dest_id': dest.id,
                'origin': rec.name,
                'note': rec.note or False,
                'company_id': rec.company_id.id or self.env.company.id,
                'x_employee_id': rec.employee_id.id,
            }
            picking = self.env['stock.picking'].create(picking_vals)

            move_vals = {
                'name': rec.product_id.display_name,
                'product_id': rec.product_id.id,
                'product_uom_qty': rec.product_uom_qty,
                'product_uom': rec.product_id.uom_id.id,
                'location_id': source.id,
                'location_dest_id': dest.id,
                'picking_id': picking.id,
                'company_id': rec.company_id.id or self.env.company.id,
            }
            StockMove.create(move_vals)

            picking.action_confirm()
            try:
                picking.action_assign()
            except Exception as e:

                try:
                    self.env['ir.logging'].sudo().create({
                        'name': 'employee_item_request.assign',
                        'type': 'server',
                        'dbname': self.env.cr.dbname,
                        'message': 'Could not assign picking %s: %s' % (picking.id, str(e)),
                        'level': 'ERROR',
                        'path': 'employee.item.request',
                        'func': 'action_approve',
                        'line': '0',
                        'exception': traceback.format_exc(),
                    })
                except Exception:
                    pass

            rec.picking_id = picking.id
            rec.state = 'approved'
        return True

    def action_done(self):
        for rec in self:
            if rec.picking_id and rec.picking_id.state != 'done':
                raise exceptions.UserError(_('Validate the transfer first.'))
            rec.state = 'done'
        return True

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'
        return True
