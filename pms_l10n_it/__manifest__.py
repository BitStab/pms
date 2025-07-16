# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "PMS Italian Guest Registration (Alloggiati Web) - Enhanced",
    "summary": """
        Complete Italian guest registration integration for PMS with Alloggiati Web service,
        including remote check-in, automatic receipt download, and comprehensive monitoring
    """,
    "version": "16.0.2.0.0",
    "license": "AGPL-3",
    "author": "Your Company, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/pms",
    "category": "Hospitality/Hotels",
    "depends": [
        "pms",
        "mail",
        "base_address_extended",
        "website",  # For remote check-in portal
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        "security/pms_l10n_it_security.xml",
        
        # Data
        "data/cron_data.xml",
        "data/enhanced_cron_data.xml",
        "data/email_templates.xml",
        
        # Views - Core Models
        "views/res_geo_views.xml",
        "views/alloggiati_tables_views.xml",
        "views/pms_property_views.xml",
        "views/pms_checkin_partner_views.xml",
        "views/pms_guest_registration_views.xml",
        
        # Views - Enhanced Features
        "views/pms_guest_registration_dashboard_views.xml",
        "views/remote_checkin_templates.xml",
        "views/pms_guest_group_views.xml",
        "views/pms_checkin_partner_groups_views.xml",
        
        # Wizards
        "wizard/pms_guest_registration_wizard_views.xml",
        "wizard/alloggiati_csv_import_wizard_views.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "external_dependencies": {
        "python": ["requests", "lxml"],
    },
    "post_init_hook": "post_init_hook",
    "development_status": "Beta",
    "maintainers": ["your_maintainer_handle"],
    "images": [
        "static/description/banner.png",
        "static/description/dashboard.png",
        "static/description/remote_checkin.png",
    ],
    "sequence": 150,
    "cloc_exclude": [
        "static/**/*",
        "demo/**/*",
    ],
}