from odoo import models, api, fields

class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            product = move.product_id
            # check reorder rules for this product
            rules = self.env['stock.reorder.rule'].search([('item_id', '=', product.id)])
            if rules:
                soh = product.qty_available
                for r in rules:
                    if soh <= r.min_qty:
                        product.message_post(body=f"⚠️ Low stock: {product.display_name} on hand: {soh} <= min {r.min_qty}")
        return moves