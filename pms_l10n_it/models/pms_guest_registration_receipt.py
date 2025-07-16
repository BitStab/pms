# Copyright 2024 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging
from datetime import datetime, timedelta
import requests
import base64

_logger = logging.getLogger(__name__)


class PmsGuestRegistrationReceipt(models.Model):
    _name = "pms.guest.registration.receipt"
    _description = "Italian Guest Registration Receipt"
    _order = "receipt_date desc"    
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Receipt Name",
        compute="_compute_name",
        store=True
    )
    
    property_id = fields.Many2one(
        "pms.property",
        string="Property",
        required=True,
        ondelete="cascade"
    )
    
    receipt_date = fields.Date(
        string="Receipt Date",
        required=True,
        index=True
    )
    
    registration_id = fields.Many2one(
        "pms.guest.registration",
        string="Related Registration",
        ondelete="cascade"
    )
    
    pdf_content = fields.Binary(
        string="PDF Content",
        attachment=True
    )
    
    pdf_filename = fields.Char(
        string="PDF Filename"
    )
    
    download_date = fields.Datetime(
        string="Download Date",
        default=fields.Datetime.now,
        readonly=True
    )
    
    state = fields.Selection([
        ('downloaded', 'Downloaded'),
        ('processed', 'Processed'),
        ('error', 'Error'),
    ], string="Status", default='downloaded')
    
    error_message = fields.Text(
        string="Error Message",
        readonly=True
    )
    
    guest_count = fields.Integer(
        string="Guest Count",
        help="Number of guests in this receipt"
    )
    
    @api.depends('property_id', 'receipt_date')
    def _compute_name(self):
        for record in self:
            if record.property_id and record.receipt_date:
                record.name = f"{record.property_id.name} - {record.receipt_date.strftime('%d/%m/%Y')}"
            else:
                record.name = _("New Receipt")
    
    @api.model
    def _cron_download_receipts(self):
        """Cron job to download receipts from Alloggiati Web"""
        properties = self.env['pms.property'].search([
            ('it_guest_registration_enabled', '=', True)
        ])
        
        # Check for receipts from the last 30 days
        start_date = fields.Date.today() - timedelta(days=30)
        
        for property_rec in properties:
            try:
                current_date = start_date
                while current_date < fields.Date.today():
                    # Check if receipt already exists for this date
                    existing_receipt = self.search([
                        ('property_id', '=', property_rec.id),
                        ('receipt_date', '=', current_date),
                        ('state', '!=', 'error')
                    ])
                    
                    if not existing_receipt:
                        self._download_receipt_for_date(property_rec, current_date)
                    
                    current_date += timedelta(days=1)
                    
            except Exception as e:
                _logger.error(
                    "Error downloading receipts for property %s: %s",
                    property_rec.name, str(e)
                )
    
    def _download_receipt_for_date(self, property_rec, receipt_date):
        """Download receipt for a specific date"""
        try:
            # Create temporary registration object for API access
            temp_registration = self.env['pms.guest.registration'].new({
                'property_id': property_rec.id,
                'registration_date': receipt_date,
            })
            
            # Get authentication token
            token_info = temp_registration._get_authentication_token()
            if not token_info.get('success'):
                _logger.warning(
                    "Failed to get auth token for property %s: %s",
                    property_rec.name, token_info.get('error')
                )
                return
            
            # Download receipt
            pdf_content = self._download_receipt_pdf(
                property_rec, token_info['token'], receipt_date
            )
            
            if pdf_content:
                # Create receipt record
                receipt = self.create({
                    'property_id': property_rec.id,
                    'receipt_date': receipt_date,
                    'pdf_content': base64.b64encode(pdf_content).decode('utf-8'),
                    'pdf_filename': f"ricevuta_{property_rec.name}_{receipt_date.strftime('%Y%m%d')}.pdf",
                    'state': 'downloaded',
                })
                
                _logger.info(
                    "Downloaded receipt for property %s, date %s",
                    property_rec.name, receipt_date
                )
                
                return receipt
                
        except Exception as e:
            _logger.error(
                "Error downloading receipt for property %s, date %s: %s",
                property_rec.name, receipt_date, str(e)
            )
            
            # Create error record
            self.create({
                'property_id': property_rec.id,
                'receipt_date': receipt_date,
                'state': 'error',
                'error_message': str(e),
            })
    
    def _download_receipt_pdf(self, property_rec, token, receipt_date):
        """Download PDF receipt from Alloggiati Web"""
        try:
            username = property_rec.alloggiati_web_username
            
            # Format date for SOAP request
            formatted_date = receipt_date.strftime('%Y-%m-%dT00:00:00')
            
            # Prepare SOAP envelope for Receipt method
            soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:all="AlloggiatiService">
    <soap:Header/>
    <soap:Body>
        <all:Ricevuta>
            <all:Utente>{username}</all:Utente>
            <all:token>{token}</all:token>
            <all:Data>{formatted_date}</all:Data>
        </all:Ricevuta>
    </soap:Body>
</soap:Envelope>"""
            
            url = "https://alloggiatiweb.poliziadistato.it/service/service.asmx"
            headers = {
                'Content-Type': 'application/soap+xml; charset=utf-8',
                'SOAPAction': 'AlloggiatiService/Ricevuta'
            }
            
            if property_rec.alloggiati_web_test_mode:
                return None  # Skip download in test mode
            
            response = requests.post(url, data=soap_envelope, headers=headers, timeout=60)
            
            if response.status_code == 200:
                return self._extract_pdf_from_response(response.text)
            else:
                _logger.error(
                    "HTTP error %s downloading receipt for date %s",
                    response.status_code, receipt_date
                )
                return None
                
        except requests.exceptions.RequestException as e:
            _logger.error(
                "Network error downloading receipt for date %s: %s",
                receipt_date, str(e)
            )
            return None
        except Exception as e:
            _logger.error(
                "Unexpected error downloading receipt for date %s: %s",
                receipt_date, str(e)
            )
            return None
    
    def _extract_pdf_from_response(self, response_text):
        """Extract PDF content from SOAP response"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response_text)
            
            # Look for PDF element
            for elem in root.iter():
                if 'PDF' in elem.tag:
                    if elem.text:
                        return base64.b64decode(elem.text)
            
            return None
            
        except Exception as e:
            _logger.error("Error extracting PDF from response: %s", str(e))
            return None
    
    def action_download_receipt(self):
        """Manual download of receipt"""
        self.ensure_one()
        
        if self.state == 'downloaded':
            raise UserError(_("Receipt already downloaded"))
        
        receipt = self._download_receipt_for_date(self.property_id, self.receipt_date)
        
        if receipt:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Receipt Downloaded'),
                    'message': _('Receipt downloaded successfully!'),
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Download Failed'),
                    'message': _('Failed to download receipt'),
                    'type': 'danger',
                }
            }
    
    def action_view_pdf(self):
        """View downloaded PDF"""
        self.ensure_one()
        
        if not self.pdf_content:
            raise UserError(_("No PDF content available"))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/pms.guest.registration.receipt/{self.id}/pdf_content/{self.pdf_filename}',
            'target': 'new',
        }