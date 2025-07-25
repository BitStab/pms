# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from . import models
from . import wizards
# from odoo import api, SUPERUSER_ID
# import logging

# _logger = logging.getLogger(__name__)


# def post_init_hook(cr, registry):
#     """Post-installation hook to initialize Italian guest registration data"""
    
#     env = api.Environment(cr, SUPERUSER_ID, {})
    
#     # Set default values for existing properties
#     properties = env['pms.property'].search([])
#     for prop in properties:
#         if not prop.exempt_minors_under_age:
#             prop.exempt_minors_under_age = 14
    
#     # Initialize country codes for Italy
#     italy = env['res.country'].search([('code', '=', 'IT')], limit=1)
#     if italy and not italy.alloggiati_web_code:
#         italy.alloggiati_web_code = '100000001'
#         italy.alloggiati_web_active = True
    
#     # Common European countries
#     country_codes = {
#         'DE': '100000002',  # Germany
#         'FR': '100000003',  # France
#         'ES': '100000004',  # Spain
#         'AT': '100000005',  # Austria
#         'CH': '100000006',  # Switzerland
#         'US': '100000007',  # United States
#         'GB': '100000008',  # United Kingdom
#     }
    
#     for code, alloggiati_code in country_codes.items():
#         country = env['res.country'].search([('code', '=', code)], limit=1)
#         if country and not country.alloggiati_web_code:
#             country.alloggiati_web_code = alloggiati_code
#             country.alloggiati_web_active = True
    
#     _logger.info("Italian guest registration module initialized successfully")