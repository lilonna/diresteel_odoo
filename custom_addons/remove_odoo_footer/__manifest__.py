{
    'name': 'Remove Odoo Footer',
    'version': '1.0',
    'summary': 'Remove Powered by Odoo from login, signup, and database pages',
    'author': 'lilo',
    'depends': ['web', 'auth_signup'],
    'data': [
        'views/auth_signup_login_templates.xml',
    ],
    'installable': True,
    'application': False,
}
