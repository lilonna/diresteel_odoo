from odoo import models, fields, api

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    stock_location_id = fields.Many2one(
        'stock.location',
        string='Department Stock Location',
        help='Stock location assigned to this department (optional).',
        readonly=True,
    )

    def ensure_stock_location(self):
        for dept in self:
            if not dept.stock_location_id:
                location_name = f"{dept.name} Location"
                existing = self.env['stock.location'].search([('name', '=', location_name)], limit=1)
                if existing:
                    dept.stock_location_id = existing
                else:
                    dept.stock_location_id = self.env['stock.location'].create({
                        'name': location_name,
                        'usage': 'internal',
                    })

    @api.model
    def auto_link_existing_locations(self):
        departments = self.search([('stock_location_id', '=', False)])
        for dept in departments:
            location_name = f"{dept.name} Location"
            existing = self.env['stock.location'].search([('name', '=', location_name)], limit=1)
            if existing:
                dept.stock_location_id = existing
