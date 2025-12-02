{
    'name': "Inventory Steel Management",
    'version': '1.0',
    'summary': "Inventory for steel manufacturing – batch tracking, reorder, costing",
    'description': """Inventory Management for steel products.
Features:
 - Batch tracking
 - Reorder rules
 - Integration with stock, purchase, mrp, account
""",
    'author': "Agape Technologies",
    'license': "LGPL-3",
    'depends': ['stock', 'purchase', 'mrp', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/batch_view.xml',
        'views/reorder_view.xml',
        'views/product_inherit_view.xml'
    ],
    'installable': True,
    'application': True
}