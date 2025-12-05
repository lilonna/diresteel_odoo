from odoo import models, fields, api, exceptions, _

class EmployeeItemRequest(models.Model):
    _name = 'employee.item.request'
    _description = 'Employee Item Request'
    _order = 'id desc'

    name = fields.Char(string='Request Reference', default='New', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', required=True, domain=[('type','=','product')])
    product_uom_qty = fields.Float(string='Quantity', required=True, default=1.0)
    employee_id = fields.Many2one('hr.employee', string='Requested For', required=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True)
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user.id, readonly=True)
    requested_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    picking_id = fields.Many2one('stock.picking', readonly=True)
    state = fields.Selection([
        ('draft','Draft'),
        ('requested','Requested'),
        ('approved','Approved'),
        ('done','Done'),
        ('cancel','Cancelled')
    ], default='draft')
    note = fields.Text()
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model
    def create(self, vals):
        if vals.get('name','New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('employee.item.request') or 'REQ/0000'
        if 'company_id' not in vals:
            vals['company_id'] = self.env.company.id
        return super().create(vals)

    def action_request(self):
        for rec in self:
            if not self.env.user.has_group('employee_item_request.group_department_head_requester'):
                raise exceptions.AccessError(_("Only department heads can submit requests."))
        self.write({'state':'requested'})
        return True

    def _select_picking_type_for_location(self, location):
        PickingType = self.env['stock.picking.type']
        if not location:
            return PickingType.search([('code','=','internal')], limit=1)
        return PickingType.search([('code','=','internal')], limit=1)

    def action_approve(self):
        if not (self.env.user.has_group('stock.group_stock_user') or self.env.user.has_group('base.group_system')):
            raise exceptions.AccessError(_('You are not allowed to approve requests.'))

        StockMove = self.env['stock.move']

        source = self.env.ref('stock.stock_location_stock', False)
        dest = self.env.ref('employee_item_request.loc_issued_items', False)

        if not source or not dest:
            raise exceptions.UserError(_('Source or destination location missing.'))

        for rec in self:
            if rec.state != 'requested':
                raise exceptions.UserError(_('Only Requested state can be approved.'))

            available = rec.product_id.with_context(location=source.id).qty_available
            if available < rec.product_uom_qty:
                raise exceptions.UserError(
                    _('Not enough stock. Available %s, Requested %s') %
                    (available, rec.product_uom_qty)
                )

            picking_type = self._select_picking_type_for_location(source)
            if not picking_type:
                raise exceptions.UserError(_('Internal picking type missing.'))

            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': source.id,
                'location_dest_id': dest.id,
                'origin': rec.name,
                'note': rec.note,
                'company_id': rec.company_id.id,
                'x_employee_id': rec.employee_id.id,
            })

            StockMove.create({
                'name': rec.product_id.display_name,
                'product_id': rec.product_id.id,
                'product_uom_qty': rec.product_uom_qty,
                'product_uom': rec.product_id.uom_id.id,
                'location_id': source.id,
                'location_dest_id': dest.id,
                'picking_id': picking.id,
                'company_id': rec.company_id.id,
            })

            picking.action_confirm()
            picking.action_assign()

            rec.write({'picking_id': picking.id, 'state':'approved'})
        return True

    def action_done(self):
        for rec in self:
            if rec.picking_id and rec.picking_id.state != 'done':
                raise exceptions.UserError(_('Validate transfer first.'))
            rec.state = 'done'
        return True

    def action_cancel(self):
        self.write({'state':'cancel'})
        return True
