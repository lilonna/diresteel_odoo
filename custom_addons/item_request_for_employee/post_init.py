from odoo import api, SUPERUSER_ID

def auto_link_departments(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    HrDept = env['hr.department']
    HrDept.auto_link_existing_locations()

    group = env.ref('item_request_for_employee.group_department_head', raise_if_not_found=False)
    model = env['ir.model'].search([('model', '=', 'department.item.request')], limit=1)

    if model and group:
        env['ir.rule'].create({
            'name': 'Department Head: view own department requests',
            'model_id': model.id,
            'groups': [(4, group.id)],
            'domain_force': "[('department_id.manager_id.user_id','=', user.id)]",
        })
