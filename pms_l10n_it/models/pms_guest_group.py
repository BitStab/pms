# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)

class PmsGuestGroup(models.Model):
    _name = "pms.guest.group"
    _description = "Guest Group for Italian Registration"
    
    reservation_id = fields.Many2one(
        "pms.reservation", 
        string="Reservation", 
        required=True
    )
    
    group_type = fields.Selection([
        ('family', 'Family (Famiglia)'),
        ('group', 'Travel Group (Gruppo)'),
        ('individual', 'Individual')
    ], string="Group Type", required=True)
    
    main_guest_id = fields.Many2one(
        "pms.checkin.partner",
        string="Main Guest (Capo)",
        required=True
    )
    
    dependent_guest_ids = fields.One2many(
        "pms.checkin.partner",
        "guest_group_id",
        string="Dependent Guests"
    )
    
    def _determine_group_type(self):
        """Automatische Erkennung Familie vs. Gruppe"""
        guests = self.reservation_id.checkin_partner_ids
        
        # Familie: Gleicher Nachname oder Verwandtschaft
        if self._is_family(guests):
            return 'family'
        
        # Gruppe: Mehrere Personen, verschiedene Namen
        if len(guests) > 1:
            return 'group'
            
        return 'individual'
    
    def _is_family(self, guests):
        """Erkennung Familie basierend auf Nachnamen"""
        if len(guests) <= 1:
            return False
            
        # Gleicher Nachname = Familie
        lastnames = set(guest.lastname for guest in guests if guest.lastname)
        return len(lastnames) == 1 and len(guests) > 1