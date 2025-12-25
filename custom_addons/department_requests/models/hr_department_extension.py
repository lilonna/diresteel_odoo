from odoo import models, fields

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    department_location_id = fields.Many2one(
        'stock.location',
        string="Department Stock Location",
        help="Internal stock location for this department."
    )
