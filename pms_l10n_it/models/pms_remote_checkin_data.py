# Copyright 2025 IT-Stecher
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class PmsRemoteCheckinData(models.Model):
    _name = "pms.remote.checkin.data"
    _description = "Remote Check-in Guest Data"
    _order = "create_date desc"
    _rec_name = "display_name"
    
    # Link to token
    token_id = fields.Many2one(
        "pms.remote.checkin.token",
        string="Check-in Token",
        required=True,
        ondelete="cascade"
    )
    
    # Guest personal information
    firstname = fields.Char(
        string="First Name",
        required=True
    )
    
    lastname = fields.Char(
        string="Last Name",
        required=True
    )
    
    birthdate_date = fields.Date(
        string="Birth Date",
        required=True
    )
    
    gender = fields.Selection([
        ('M', 'Male'),
        ('F', 'Female'),
    ], string="Gender", required=True)
    
    nationality_id = fields.Many2one(
        "res.country",
        string="Nationality",
        required=True
    )
    
    # Residence information
    residence_country_id = fields.Many2one(
        "res.country",
        string="Country of Residence",
        required=True
    )
    
    residence_state_id = fields.Many2one(
        "res.country.state",
        string="State of Residence"
    )
    
    residence_city_id = fields.Many2one(
        "res.city",
        string="City of Residence"
    )
    
    # Document information
    document_type = fields.Selection([
        ('passport', 'Passport'),
        ('id_card', 'ID Card'),
        ('driving_license', 'Driving License'),
        ('other', 'Other'),
    ], string="Document Type", required=True)
    
    document_number = fields.Char(
        string="Document Number",
        required=True
    )
    
    document_expedition_date = fields.Date(
        string="Document Issue Date",
        required=True
    )
    
    document_expiry_date = fields.Date(
        string="Document Expiry Date"
    )
    
    # Contact information
    email = fields.Char(
        string="Email"
    )
    
    phone = fields.Char(
        string="Phone"
    )
    
    # Stay information
    arrival = fields.Date(
        string="Arrival Date"
    )
    
    departure = fields.Date(
        string="Departure Date"
    )
    
    # Privacy and consent
    privacy_consent = fields.Boolean(
        string="Privacy Consent",
        required=True,
        help="Guest has consented to data processing"
    )
    
    marketing_consent = fields.Boolean(
        string="Marketing Consent",
        help="Guest has consented to marketing communications"
    )
    
    # Additional fields for Italian registration
    place_of_birth = fields.Char(
        string="Place of Birth",
        help="City or place where the guest was born"
    )
    
    document_issue_place = fields.Char(
        string="Document Issue Place",
        help="Place where the document was issued"
    )
    
    # Computed fields
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True
    )
    
    is_complete = fields.Boolean(
        string="Is Complete",
        compute="_compute_is_complete",
        store=True
    )

    is_main_guest = fields.Boolean(
        string="Main Guest",
        default=False,
        help="Indicates if this guest is the main guest in a group"
    )
    
    # Status fields
    is_transferred = fields.Boolean(
        string="Transferred to Check-in Partner",
        default=False,
        readonly=True
    )
    
    transferred_date = fields.Datetime(
        string="Transferred Date",
        readonly=True
    )
    
    checkin_partner_id = fields.Many2one(
        "pms.checkin.partner",
        string="Check-in Partner",
        readonly=True
    )
    
    @api.depends('firstname', 'lastname')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.firstname or ''} {record.lastname or ''}".strip()
    
    @api.depends('firstname', 'lastname', 'birthdate_date', 'gender', 
                 'nationality_id', 'document_type', 'document_number',
                 'document_expedition_date', 'residence_country_id')
    def _compute_is_complete(self):
        """Check if all required fields are filled"""
        for record in self:
            record.is_complete = bool(
                record.firstname and
                record.lastname and
                record.birthdate_date and
                record.gender and
                record.nationality_id and
                record.document_type and
                record.document_number and
                record.document_expedition_date and
                record.residence_country_id and
                record.privacy_consent
            )
    
    @api.onchange('residence_country_id')
    def _onchange_residence_country_id(self):
        """Clear state and city when country changes"""
        if self.residence_country_id:
            self.residence_state_id = False
            self.residence_city_id = False
    
    @api.onchange('residence_state_id')
    def _onchange_residence_state_id(self):
        """Clear city when state changes"""
        if self.residence_state_id:
            self.residence_city_id = False
    
    @api.constrains('birthdate_date')
    def _check_birthdate(self):
        """Validate birthdate is not in the future"""
        for record in self:
            if record.birthdate_date and record.birthdate_date > fields.Date.today():
                raise ValidationError(_("Birth date cannot be in the future."))
    
    @api.constrains('document_expedition_date', 'document_expiry_date')
    def _check_document_dates(self):
        """Validate document dates"""
        for record in self:
            if record.document_expedition_date and record.document_expedition_date > fields.Date.today():
                raise ValidationError(_("Document issue date cannot be in the future."))
            
            if record.document_expiry_date:
                if record.document_expiry_date < fields.Date.today():
                    raise ValidationError(_("Document has expired."))
                
                if record.document_expedition_date and record.document_expiry_date <= record.document_expedition_date:
                    raise ValidationError(_("Document expiry date must be after issue date."))

    def _transfer_to_checkin_partner(self, checkin_partner):
        """
        Transfer data from remote check-in data to pms.checkin.partner
        
        :param checkin_partner: pms.checkin.partner record to update
        """
        self.ensure_one()
        
        if not checkin_partner:
            raise UserError(_("No check-in partner provided"))
        
        # Prepare values to transfer
        vals = {}
        
        # Personal information
        if self.birthdate_date:
            vals['birthdate_date'] = self.birthdate_date
        
        if self.gender:
            vals['gender'] = self.gender
        
        # Contact information
        if self.email:
            vals['email'] = self.email
        
        if self.phone:
            vals['mobile'] = self.phone
        
        # Nationality
        if self.nationality_id:
            vals['nationality_id'] = self.nationality_id.id
        
        # Document information
        if self.document_type:
            vals['document_type'] = self.document_type
        
        if self.document_number:
            vals['document_number'] = self.document_number
        
        if self.document_expedition_date:
            vals['document_expedition_date'] = self.document_expedition_date
        
        if self.document_expiry_date:
            vals['document_expiry_date'] = self.document_expiry_date
        
        # Residence information
        if self.residence_country_id:
            vals['residence_country_id'] = self.residence_country_id.id
        
        if self.residence_state_id:
            vals['residence_state_id'] = self.residence_state_id.id
        
        if self.residence_city_id:
            vals['residence_city_id'] = self.residence_city_id.id
        
        # Italian specific fields
        if self.place_of_birth:
            vals['place_of_birth'] = self.place_of_birth
        
        if self.document_issue_place:
            vals['document_issue_place'] = self.document_issue_place
        
        # Stay information - only update if not already set
        if self.arrival and not checkin_partner.arrival:
            vals['arrival'] = self.arrival
        
        if self.departure and not checkin_partner.departure:
            vals['departure'] = self.departure
        
        # Update check-in state if we have complete data
        if self.is_complete and checkin_partner.state == 'draft':
            vals['state'] = 'onboard'
        
        # Mark that remote check-in was completed
        vals['self_checkin_completed'] = True
        vals['self_checkin_date'] = fields.Datetime.now()
        
        # Update the checkin partner
        checkin_partner.write(vals)
        
        # Mark this data as transferred
        self.write({
            'is_transferred': True,
            'transferred_date': fields.Datetime.now(),
            'checkin_partner_id': checkin_partner.id,
        })
        
        # Check for Italian registration exemptions
        if checkin_partner.reservation_id.pms_property_id.it_guest_registration_enabled:
            # Auto-exempt minors under 14
            if checkin_partner.birthdate_date:
                age = (fields.Date.today() - checkin_partner.birthdate_date).days / 365.25
                if age < 14 and not checkin_partner.it_exemption_reason:
                    checkin_partner.write({
                        'it_exemption_reason': 'minor',
                        'it_exemption_notes': _('Automatically exempted: Minor under 14 years')
                    })
        
        _logger.info(
            "Transferred remote check-in data for %s to check-in partner %s",
            self.display_name,
            checkin_partner.display_name
        )
        
        return True