# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)


class ResCountry(models.Model):
    _inherit = "res.country"

    alloggiati_web_code = fields.Char(
        string="Alloggiati Web Code",
        size=9,
        help="Official country code used by Italian Police Alloggiati Web system"
    )
    
    alloggiati_web_active = fields.Boolean(
        string="Active in Alloggiati Web",
        default=False,
        help="Indicates if this country is recognized by Alloggiati Web system"
    )
    
    @api.model
    def get_alloggiati_code(self, country_id=None):
        """Get Alloggiati Web code for a country"""
        if not country_id:
            return "000000000"
        
        if isinstance(country_id, int):
            country = self.browse(country_id)
        else:
            country = country_id
            
        if country and country.alloggiati_web_code:
            return country.alloggiati_web_code
        
        # Fallback to default mappings if not configured
        default_mappings = {
            "IT": "100000001",  # Italy
            "DE": "100000002",  # Germany
            "FR": "100000003",  # France
            "ES": "100000004",  # Spain
            "AT": "100000005",  # Austria
            "CH": "100000006",  # Switzerland
            "US": "100000007",  # United States
            "GB": "100000008",  # United Kingdom
        }
        
        return default_mappings.get(country.code, "100000000") if country else "000000000"


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    alloggiati_web_code = fields.Char(
        string="Alloggiati Web Code",
        size=9,
        help="Official province/state code used by Italian Police Alloggiati Web system"
    )
    
    alloggiati_web_active = fields.Boolean(
        string="Active in Alloggiati Web",
        default=False,
        help="Indicates if this province/state is recognized by Alloggiati Web system"
    )
    
    @api.model
    def get_alloggiati_code(self, state_id=None):
        """Get Alloggiati Web code for a state/province"""
        if not state_id:
            return "000000000"
        
        if isinstance(state_id, int):
            state = self.browse(state_id)
        else:
            state = state_id
            
        if state and state.alloggiati_web_code:
            return state.alloggiati_web_code
            
        return "000000000"


class ResCity(models.Model):
    _inherit = "res.city"

    alloggiati_web_code = fields.Char(
        string="Alloggiati Web Code",
        size=9,
        help="Official city/comune code used by Italian Police Alloggiati Web system"
    )
    
    alloggiati_web_active = fields.Boolean(
        string="Active in Alloggiati Web",
        default=False,
        help="Indicates if this city/comune is recognized by Alloggiati Web system"
    )
    
    istat_code = fields.Char(
        string="ISTAT Code",
        size=6,
        help="Official ISTAT code for Italian municipalities"
    )
    
    cadastral_code = fields.Char(
        string="Cadastral Code",
        size=4,
        help="Italian cadastral code (Codice Catastale)"
    )
    
    @api.model
    def get_alloggiati_code(self, city_id=None):
        """Get Alloggiati Web code for a city"""
        if not city_id:
            return "000000000"
        
        if isinstance(city_id, int):
            city = self.browse(city_id)
        else:
            city = city_id
            
        if city and city.alloggiati_web_code:
            return city.alloggiati_web_code
            
        return "000000000"
    
    @api.model
    def search_by_istat_code(self, istat_code):
        """Find city by ISTAT code"""
        return self.search([('istat_code', '=', istat_code)], limit=1)
    
    @api.model
    def search_by_cadastral_code(self, cadastral_code):
        """Find city by cadastral code"""
        return self.search([('cadastral_code', '=', cadastral_code)], limit=1)