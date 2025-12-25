from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    employee_issue_type = fields.Selection([
        ('consumable', 'Consumable'),
        ('returnable', 'Returnable / Asset'),
    ],string="Employee Issue Type", required=True, default='consumable',help="Defines whether the product is issued as a consumable or a returnable asset.")


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    stock_location_id = fields.Many2one(
        'stock.location',
        string='Department Stock Location',
        help='Internal stock location used for returnable items.'
    )
    
    def _get_or_create_consumable_location(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        
        location = self.env['stock.location'].search([
            ('usage', '=', 'inventory'),
            ('name', '=', 'Employee Consumption'),
            ('company_id', '=', company.id),
        ], limit=1)
        
        if not location:
            location = self.env['stock.location'].create({
                'name': 'Employee Consumption',
                'usage': 'inventory',  
                'company_id': company.id,
            })
        return location

    def get_or_create_stock_location(self):
        self.ensure_one()

        if self.stock_location_id:
            return self.stock_location_id

        company = self.company_id or self.env.company
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id)
        ], limit=1)
        if not warehouse or not warehouse.lot_stock_id:
            raise UserError(_('No warehouse or stock location found for company %s') % company.name)

        parent_loc = warehouse.lot_stock_id

        location = self.env['stock.location'].search([
            ('name', '=', self.name),
            ('usage', '=', 'internal'),
            ('location_id', '=', parent_loc.id),
            ('company_id', '=', company.id),
        ], limit=1)

        if not location:
            location = self.env['stock.location'].create({
                'name': self.name or f'Department-{self.id}',
                'usage': 'internal',
                'location_id': parent_loc.id,
                'company_id': company.id,
            })

        self.stock_location_id = location.id
        return location

class EmployeeAssetCard(models.Model):
    _name = 'employee.asset.card'
    _description = 'Employee Asset Card'

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', required=True)
    line_ids = fields.One2many('employee.asset.card.line', 'card_id')

    @api.depends('employee_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f"Asset Card - {rec.employee_id.display_name}"

class EmployeeAssetCardLine(models.Model):
    _name = 'employee.asset.card.line'
    _description = 'Employee Asset Card Line'

    card_id = fields.Many2one('employee.asset.card', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(default=1.0)
    issue_date = fields.Datetime(default=fields.Datetime.now)

    returnable = fields.Boolean()
    returned = fields.Boolean(default=False)

    request_id = fields.Many2one('department.item.request')
    return_picking_id = fields.Many2one('stock.picking', readonly=True)

    return_date = fields.Datetime(string='Returned On', readonly=True)

    condition_on_return = fields.Selection([
        ('good', 'Good'),
        ('repair', 'Needs Repair'),
        ('scrap', 'Damaged / Scrap'),
        ('lost', 'Lost'),
    ], string='Return Condition')

    return_notes = fields.Text()

    def action_open_return_wizard(self):
        self.ensure_one()
        if self.returned:
            raise UserError(_('Product is already returned'))

        return {
            'name': _('Return Asset'),
            'type': 'ir.actions.act_window',
            'res_model': 'employee.asset.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_line_id': self.id,
            }
        }

    def _get_or_create_location(self, name, usage):
        location = self.env['stock.location'].search([
            ('name', '=', name),
            ('usage', '=', usage),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if not location:
            location = self.env['stock.location'].create({
                'name': name,
                'usage': usage,
                'company_id': self.env.company.id,
            })
        return location

    def _get_return_destination_location(self, condition):
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not warehouse or not warehouse.lot_stock_id:
            raise UserError(_('Warehouse or main stock location not found'))

        if condition == 'good':
            return warehouse.lot_stock_id

        if condition == 'repair':
            return self._get_or_create_location('Repair', 'internal')

        if condition == 'scrap':
            return self._get_or_create_location('Scrap', 'inventory')

        return False
  
class EmployeeAssetReturnWizard(models.TransientModel):
    _name = 'employee.asset.return.wizard'
    _description = 'Return Employee Asset'
    asset_line_id =fields.Many2one(
        'employee.asset.card.line', required = True
    )
    condition = fields.Selection([
        ('good' , 'Good'),
        ('repair' , 'Needs Repair'),
        ('scrap' , 'Damaged/Scrap'),
        ('lost', 'Lost'),
    ], required = True)
    notes = fields.Text()
    
    def action_confirm_return(self):
        self.ensure_one()
        
        line = self.asset_line_id
        
        if line.returned:
            raise UserError(_('This Product is already returned'))
        
        if self.condition == 'lost':
            line.write({
                'returned': True,
                'return_date': fields.Datetime.now(),
                'condition_on_return':self.condition,
                'return_notes': self.notes,
            })
            return {'type': 'ir.actions.act_window_close'}
        dest_location = line._get_return_destination_location(self.condition)
        if not dest_location:
            raise UserError(_('destination locatin not found'))
        
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.env.company.id),
        ], limit =1 )
        
        if not warehouse:
            raise UserError(_('no warehouse found'))
        
        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'internal')
        ],limit = 1) 
        
        if not picking_type:
            raise UserError(_('no picking type found'))
        
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': line.request_id.department_id.stock_location_id.id,
            'location_dest_id': dest_location.id,
            'origin': f'Return - {line.card_id.name}',
        })  
        self.env['stock.move'].create({
            'name': line.product_id.display_name,
            'picking_id': picking.id,
            'product_id': line.product_id.id,
            'product_uom_qty': line.quantity,
            'product_uom': line.product_id.uom_id.id,
            'location_id': picking.location_id.id,
            'location_dest_id': dest_location.id,
        }) 
        picking.action_confirm()
        picking.action_assign()  
        picking.button_validate()
        line.write({
            'returned': True,
            'return_date': fields.Datetime.now(),
            'condition_on_return': self.condition,
            'return_notes': self.notes,
            'return_picking_id': picking.id,
        })
        return {'type': 'ir.actions.act_window_close'}  

class EmployeeConsumableLog(models.Model):
    _name = 'employee.consumable.log'
    _description = 'Employee Consumable Log'
    _order = 'create_date desc'

    employee_id = fields.Many2one('hr.employee', required=True)
    department_id = fields.Many2one('hr.department', required=True)
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(required=True)
    request_id = fields.Many2one('department.item.request', required=True)
    picking_id = fields.Many2one('stock.picking', required=True)
    date = fields.Datetime(default=fields.Datetime.now)

class DepartmentItemRequest(models.Model):
    _name = 'department.item.request'
    _description = 'Department Item Request'
    _order = 'id desc'

    name = fields.Char(required=True)
    department_id = fields.Many2one(
        'hr.department',
        default=lambda self: self.env.user.employee_id.department_id,
        readonly=True,
    )
    employee_id = fields.Many2one('hr.employee', required=True)
    line_ids = fields.One2many('department.item.request.line', 'request_id')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_pickup', 'Waiting Pickup'),
        ('done', 'Done'),
    ], default='draft')

    consumable_picking_id = fields.Many2one('stock.picking', readonly=True)
    returnable_picking_id = fields.Many2one('stock.picking', readonly=True)

    def action_submit_request(self):
        for req in self:
            if req.state != 'draft':
                raise UserError(_('This request has already been submitted.'))
            if not req.line_ids:
                raise UserError(_('Add at least one request line.'))

            for line in req.line_ids:
                if not line.product_uom_id:
                    raise UserError(_('Unit of Measure missing for %s') % line.product_id.display_name)
                available = getattr(line.product_id, 'free_qty', line.product_id.qty_available)
                if line.quantity > available:
                    raise UserError(_('%s: only %s units available.') % (
                        line.product_id.display_name, available
                    ))

            consumable_lines = req.line_ids.filtered(
                lambda l: l.product_id.product_tmpl_id.employee_issue_type == 'consumable'
            )
            returnable_lines = req.line_ids.filtered(
                lambda l: l.product_id.product_tmpl_id.employee_issue_type == 'returnable'
            )

            if consumable_lines:
                req.consumable_picking_id = req._create_consumable_picking(consumable_lines).id

            if returnable_lines:
                dept_loc = req.department_id.get_or_create_stock_location()
                req.returnable_picking_id = req._create_returnable_picking(returnable_lines, dept_loc).id

            req.state = 'waiting_pickup'

    def _get_warehouse(self):
        company = self.department_id.company_id or self.env.company
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id)
        ], limit=1)
        if not warehouse or not warehouse.lot_stock_id:
            raise UserError(_('No warehouse configured for company %s') % company.name)
        return warehouse

    def _create_consumable_picking(self, lines):
        warehouse = self._get_warehouse()
        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'outgoing')
        ], limit=1)
        if not picking_type:
            raise UserError(_('No outgoing picking type found.'))

        dest = self.department_id._get_or_create_consumable_location()

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': dest.id,
            'origin': self.name,
            'department_request_id': self.id,
        })

        for line in lines:
            self.env['stock.move'].create({
                'name': f"{line.product_id.display_name} (Consumption)",
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_uom_id.id,
                'location_id': warehouse.lot_stock_id.id,
                'location_dest_id': dest.id,
            })

        picking.action_confirm()
        picking.action_assign()
        return picking

    def _create_returnable_picking(self, lines, dest_location):
        warehouse = self._get_warehouse()
        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'internal')
        ], limit=1)
        if not picking_type:
            raise UserError(_('No internal picking type found.'))

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'department_request_id': self.id,
        })

        for line in lines:
            self.env['stock.move'].create({
                'name': line.product_id.display_name,
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_uom_id.id,
                'location_id': warehouse.lot_stock_id.id,
                'location_dest_id': dest_location.id,
            })

        picking.action_confirm()
        picking.action_assign()
        return picking
    def _update_state_from_pickings(self):
        for req in self:
            consumable_done = (
                not req.consumable_picking_id
                or req.consumable_picking_id.state == 'done'
            )
            returnable_done = (
                not req.returnable_picking_id
                or req.returnable_picking_id.state == 'done'
            )
            if consumable_done and returnable_done:
                req.state = 'done'        
    def _create_employee_asset_card_from_moves(self, move_lines):
        self.ensure_one()
        card = self.env['employee.asset.card'].search([
            ('employee_id', '=', self.employee_id.id)
        ], limit=1) 
        
        if not card:
            card = self.env['employee.asset.card'].create({'employee_id': self.employee_id.id})

        for ml in move_lines.filtered(lambda ml: ml.product_id.product_tmpl_id.employee_issue_type == 'returnable'):
            self.env['employee.asset.card.line'].create({
                'card_id': card.id,
                'product_id': ml.product_id.id,
                'quantity': ml.quantity or ml.product_uom_qty,
                'returnable': True,
                'request_id': self.id,
            })

class DepartmentItemRequestLine(models.Model):
    _name = 'department.item.request.line'
    _description = 'Department Item Request Line'

    request_id = fields.Many2one('department.item.request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(default=1.0, required=True)
    product_uom_id = fields.Many2one('uom.uom',related='product_id.uom_id', store= True, readonly = True)
    warning_message = fields.Char(readonly=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            self.warning_message = False

    @api.onchange('quantity')
    def _onchange_quantity(self):
        if self.product_id and self.quantity:
            available = getattr(self.product_id, 'free_qty', self.product_id.qty_available)
            if self.quantity > available:
                self.warning_message = _(
                    'Only %s units available.'
                ) % available
            else:
                self.warning_message = False

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    department_request_id = fields.Many2one('department.item.request')

    def button_validate(self):
        res = super().button_validate()
        for picking in self:             
            req = picking.department_request_id
            if not req:
                continue
            move_lines = picking.move_line_ids.filtered(lambda ml: ml.quantity)
            if not move_lines:
                move_lines = picking.move_ids_without_package
            for ml in move_lines.filtered(lambda ml: ml.product_id.product_tmpl_id.employee_issue_type == 'consumable'):
                self.env['employee.consumable.log'].create({
                    'employee_id': req.employee_id.id,
                    'department_id': req.department_id.id,
                    'product_id': ml.product_id.id,
                    'quantity': ml.quantity or ml.product_uom_qty,
                    'request_id': req.id,
                    'picking_id': picking.id,
                }) 
            if any (ml.product_id.product_tmpl_id.employee_issue_type == 'returnable' for ml in move_lines):  
                req._create_employee_asset_card_from_moves(move_lines)
            req._update_state_from_pickings()         
        return res
