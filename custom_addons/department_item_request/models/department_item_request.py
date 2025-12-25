from odoo import models, fields, api

class DepartmentItemRequest(models.Model):
    _name = 'department.item.request'
    _description = 'Department Item Request'

    name = fields.Char(string="Request Name", required=True)

    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        readonly=True
    )

    department_id = fields.Many2one(
        'hr.department',
        string="Department",
        compute="_compute_department",
        store=True,
        readonly=True
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        domain="[('department_id', 'child_of', department_id)]"
        required=True,
        help="Employee must belong to the same department"
    )

    line_ids = fields.One2many(
        'department.item.request.line',
        'request_id',
        string="Items"
    )

    @api.depends('requested_by')
    def _compute_department(self):
        for rec in self:
            # Requested by user must be a department head or sub-head
            employee = self.env['hr.employee'].search([
                ('user_id', '=', rec.requested_by.id)
            ], limit=1)

            rec.department_id = employee.department_id.id if employee else False


class DepartmentItemRequestLine(models.Model):
    _name = 'department.item.request.line'
    _description = 'Department Item Request Line'

    request_id = fields.Many2one('department.item.request', required=True)

    product_id = fields.Many2one(
        'product.product',
        string="Product",
        required=True
    )

    quantity = fields.Float(string="Quantity", required=True, default=1.0)
