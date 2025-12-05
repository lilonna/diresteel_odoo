from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    is_department_head = fields.Boolean(
        string='Is Department Head',
        compute='_compute_is_department_head',
        store=False
    )

    @api.depends('employee_ids', 'employee_ids.parent_id')
    def _compute_is_department_head(self):
        for user in self:
            user.is_department_head = any(emp.parent_id for emp in user.employee_ids)
