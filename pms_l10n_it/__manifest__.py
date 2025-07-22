# pms_l10n_it/__manifest__.py (Finale Version)
{
    'name': 'PMS Italy Localization',
    'version': '16.0.1.0.0',
    'category': 'Hospitality',
    'summary': 'PMS Italy Localization with Alloggiati integration',
    'description': """
PMS Italian Localization
========================

This module extends the PMS (Property Management System) module with 
Italian localization features, including integration with the Italian 
Alloggiati Web service for guest registration.

Key Features:
* Italian guest registration compliance
* Alloggiati Web service integration  
* Enhanced document type management (extends PMS res.partner.id_category)
* Remote check-in functionality
* Automatic receipt download
* Guest registration dashboard

Technical Notes:
* Extends the existing PMS partner identification system
* No model duplication - uses standard res.partner.id_category
* Fully compatible with OCA PMS architecture
    """,
    "version": "16.0.2.0.0",
    "license": "AGPL-3",
    "author": "IT-Stecher",
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
        
        # Wizards - KORRIGIERTE REIHENFOLGE
        "wizards/pms_guest_registration_wizard_views.xml",
        "wizards/alloggiati_csv_import_wizard_views.xml",
        "wizards/pms_document_type_import_wizard_views.xml",  # HINZUGEFÜGT
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
    "maintainers": ["Bitstab", "IT-Stecher"],
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