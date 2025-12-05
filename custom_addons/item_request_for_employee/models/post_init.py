from odoo import api, SUPERUSER_ID

def auto_link_departments(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['hr.department'].auto_link_existing_locations()