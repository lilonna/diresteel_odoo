from odoo import http
from odoo.http import request

class InstalledAppsDashboard(http.Controller):

    @http.route('/web/login', auth='public', website=True, csrf=False)
    def web_login_redirect(self, **kw):
        if request.session.uid:
            return request.redirect('/installed_apps_dashboard')

        return request.render('web.login', kw)

    @http.route('/installed_apps_dashboard', auth='user')
    def installed_apps_dashboard(self):
        modules = request.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')],
            order='name asc'
        )
        return request.render('installed_apps_dashboard.template_dashboard', {
            'modules': modules,
        })
