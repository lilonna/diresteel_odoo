from odoo import models, fields
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_employee_id = fields.Many2one('hr.employee', string='Issued To')
    x_requested_by = fields.Many2one('res.users', string='Requested By')
    x_request_reference = fields.Char(string='Request Reference')
    x_requested_date = fields.Datetime(string='Requested On')

    def populate_from_request(self, request):
        try:
            self.x_employee_id = request.employee_id.id
            self.x_requested_by = request.requested_by_user.id
            self.x_request_reference = request.name
            self.x_requested_date = request.requested_date
            moves = []
            for line in request.line_ids:
                moves.append({
                    'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': self.location_id.id,
                    'location_dest_id': self.location_dest_id.id,
                    'department_request_line_id': line.id,
                })
            if moves:
                self.env['stock.move'].create([{
                    **m,
                    'picking_id': self.id
                } for m in moves])
        except Exception as e:
            _logger.exception('Failed to populate picking from request %s: %s', request.name, e)
            raise UserError(_('Failed to populate picking: %s') % e)
