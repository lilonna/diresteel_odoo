from odoo import models, fields

class StockBatch(models.Model):
    _name = 'stock.batch'
    _description = 'Stock Batch'

    item_id = fields.Many2one('product.product', string="Item", required=True)
    batch_no = fields.Char(required=True)
    qty = fields.Float(required=True, digits='Product Unit of Measure')
    unit_cost = fields.Monetary(required=True, currency_field='company_currency_id')
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse")
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)