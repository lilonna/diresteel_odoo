from odoo import models, fields, api, _
from odoo.exceptions import UserError

class DepartmentItemRequestLine(models.Model):
    _name = 'department.item.request.line'
    _description = 'Department Item Request Line'

    request_id = fields.Many2one('department.item.request', string='Request', ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)

    @api.constrains('quantity')
    def _check_quantity_positive(self):
        for rec in self:
            if rec.quantity <= 0:
                raise UserError(_('Quantity must be greater than 0.'))

    def _check_request_state(func):
        def wrapper(self, vals=None):
            if not self._context.get('skip_request_state_check'):
                requests_blocking = self.mapped('request_id').filtered(lambda r: r.state in ('approved', 'done'))
                if requests_blocking:
                    raise UserError(_('Cannot modify lines of a request that is approved or done.'))
            return func(self, vals)
        return wrapper

    @_check_request_state
    def write(self, vals):
        return super().write(vals)

    @_check_request_state
    def unlink(self):
        return super().unlink()