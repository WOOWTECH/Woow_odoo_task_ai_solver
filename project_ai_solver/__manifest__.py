{
    'name': 'Project AI Solver',
    'version': '18.0.1.0.0',
    'category': 'Project',
    'summary': 'Real-time chat between CS agents and portal users on project tasks',
    'description': """
        Adds a dedicated real-time chat channel to each Project Task,
        enabling direct messaging between internal CS agents and
        external portal users via Odoo's discuss.channel and bus.bus.
    """,
    'author': 'Project AI Solver',
    'license': 'LGPL-3',
    'depends': [
        'project',
        'mail',
        'bus',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/project_task_views.xml',
        'templates/portal_task_chat.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'project_ai_solver/static/src/components/task_chat/task_chat.js',
            'project_ai_solver/static/src/components/task_chat/task_chat.xml',
            'project_ai_solver/static/src/components/task_chat/task_chat.scss',
        ],
        'web.assets_frontend': [
            'project_ai_solver/static/src/portal/portal_chat.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
