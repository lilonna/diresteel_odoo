from odoo import models, fields

class StockReorderRule(models.Model):
    _name = 'stock.reorder.rule'
    _description = 'Reorder Rule'

    item_id = fields.Many2one('product.product', required=True)
    min_qty = fields.Float(required=True, digits='Product Unit of Measure')
    max_qty = fields.Float(digits='Product Unit of Measure')