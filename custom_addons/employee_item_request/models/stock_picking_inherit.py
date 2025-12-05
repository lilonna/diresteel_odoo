from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_employee_id = fields.Many2one('hr.employee', string='Issued To')
