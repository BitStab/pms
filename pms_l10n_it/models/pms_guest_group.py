# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError
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
    
    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        related="reservation_id.pms_property_id",
        store=True
    )
    
    display_name = fields.Char(
        string="Name",
        compute="_compute_display_name",
        store=True
    )
    
    guest_count = fields.Integer(
        string="Guest Count",
        compute="_compute_guest_count",
        store=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('registered', 'Registered')
    ], string="State", default='draft')

    @api.depends('main_guest_id', 'group_type', 'guest_count')
    def _compute_display_name(self):
        for group in self:
            if group.main_guest_id:
                group.display_name = f"{group.main_guest_id.display_name} ({group.group_type} - {group.guest_count} guests)"
            else:
                group.display_name = f"Guest Group ({group.group_type})"

    @api.depends('main_guest_id', 'dependent_guest_ids')
    def _compute_guest_count(self):
        for group in self:
            count = 1 if group.main_guest_id else 0  # Main guest
            count += len(group.dependent_guest_ids)   # Dependent guests
            group.guest_count = count

    def auto_create_groups(self, reservation_ids):
        """Automatically create guest groups for reservations"""
        for reservation in reservation_ids:
            if not reservation.checkin_partner_ids:
                continue
            
            main_guest = reservation.checkin_partner_ids.filtered(lambda g: g.is_main_guest)
            if not main_guest:
                continue
            
            group = reservation.env['pms.guest.group'].create({
                'reservation_id': reservation.id,
                'main_guest_id': main_guest.id,
                'group_type': 'family',  # Default to family, can be adjusted
            })
            
            # Add all other guests to the group
            other_guests = reservation.checkin_partner_ids - main_guest
            group.dependent_guest_ids = [(6, 0, other_guests.ids)]
            
            _logger.info(f"Created guest group {group.display_name} for reservation {reservation.name}")

    GROUP_TYPE_NAMES = {
        'family': _('Family (Famiglia)'),
        'group': _('Travel Group (Gruppo)'),
        'individual': _('Individual')
    }

    def action_auto_detect_group(self):
        """Automatische Erkennung des Gruppentyps"""
        self.ensure_one()
        
        all_guests = self.dependent_guest_ids + self.main_guest_id
        detected_type = self._determine_group_type(all_guests)
        
        self.write({'group_type': detected_type})
        
        # Nach dem write() hat self.group_type den neuen Wert
        field = self._fields['group_type']
        display_name = dict(field.selection)[self.group_type]
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Group Type Detected'),
                'message': _('Group type set to: %s') % display_name,
                'type': 'success',
            }
        }
    
    def _determine_group_type(self, guests):
        """Automatische Erkennung Familie vs. Gruppe"""
        if not guests:
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

    def action_confirm_group(self):
        """Bestätige die Gruppenstruktur"""
        self.ensure_one()
        
        if not self.main_guest_id:
            raise UserError(_("Please select a main guest"))
        
        if self.guest_count < 2 and self.group_type != 'individual':
            raise UserError(_("Groups must have at least 2 members"))
        
        # Stelle sicher, dass der Hauptgast korrekt markiert ist
        self.main_guest_id.write({'is_main_guest': True})
        
        # Stelle sicher, dass abhängige Gäste nicht als Hauptgast markiert sind
        self.dependent_guest_ids.write({'is_main_guest': False})
        
        self.write({'state': 'confirmed'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Group Confirmed'),
                'message': _('Guest group structure has been confirmed'),
                'type': 'success',
            }
        }