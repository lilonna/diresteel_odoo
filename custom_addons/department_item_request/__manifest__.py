{
    'name': 'Department Requests',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Department item requests workflow for department heads',
    'application': True,
    'depends': ['base', 'hr', 'stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu_home.xml',
        'views/department_item_request_views.xml',
    ],
    'installable': True,
}
