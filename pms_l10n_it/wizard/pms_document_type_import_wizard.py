# Copyright 2024 Your Company
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import csv
import io
import base64
import logging

_logger = logging.getLogger(__name__)


class DocumentTypeImportWizard(models.TransientModel):
    _name = "pms.document.type.import.wizard"
    _description = "PMS Document Type CSV Import Wizard"

    csv_file = fields.Binary(
        string="CSV File",
        required=True,
        help="Upload the documenti.csv file from Alloggiati Web"
    )
    
    csv_filename = fields.Char(
        string="Filename"
    )
    
    update_existing = fields.Boolean(
        string="Update Existing Records",
        default=True,
        help="Update existing document types with the same code"
    )
    
    deactivate_missing = fields.Boolean(
        string="Deactivate Missing Records", 
        default=False,
        help="Deactivate document types not found in the CSV file"
    )
    
    import_result = fields.Text(
        string="Import Result",
        readonly=True
    )

    def action_import_csv(self):
        """Import document types from CSV file"""
        if not self.csv_file:
            raise UserError(_("Please upload a CSV file"))
        
        try:
            # Decode the CSV file
            csv_content = base64.b64decode(self.csv_file).decode('utf-8')
            csv_reader = csv.reader(io.StringIO(csv_content), delimiter=';')
            
            # Skip header row if exists
            try:
                first_row = next(csv_reader)
                if first_row and first_row[0].lower() in ['codice', 'code']:
                    pass  # Skip header
                else:
                    # Reset reader if first row contains data
                    csv_reader = csv.reader(io.StringIO(csv_content), delimiter=';')
            except StopIteration:
                raise UserError(_("The CSV file is empty"))
            
            imported_codes = []
            created_count = 0
            updated_count = 0
            
            for row in csv_reader:
                if len(row) >= 2:
                    code = row[0].strip()
                    name = row[1].strip()
                    
                    if code and name:
                        imported_codes.append(code)
                        
            # Clear existing data for this table type and property
            existing_records = self.env['pms.document.type'].search([
                ('code', '=', code)
            ])
            
            for existing in existing_records:
                if self.update_existing:
                    existing.write({
                        'name': name,
                        'active': True
                    })
                    updated_count += 1
                else:
                    # Create new document type
                    self.env['pms.document.type'].create({
                        'code': code,
                        'name': name,
                        'active': True,
                        'sequence': len(imported_codes) * 10
                    })
                    created_count += 1
            
            # Deactivate missing records if requested
            deactivated_count = 0
            if self.deactivate_missing:
                missing_records = self.env['pms.document.type'].search([
                    ('code', 'not in', imported_codes),
                    ('active', '=', True)
                ])
                missing_records.write({'active': False})
                deactivated_count = len(missing_records)
            
            # Prepare result message
            result_lines = [
                f"Import completed successfully!",
                f"Created: {created_count} document types",
                f"Updated: {updated_count} document types",
            ]
            
            if deactivated_count > 0:
                result_lines.append(f"Deactivated: {deactivated_count} document types")
            
            self.import_result = '\n'.join(result_lines)
            
            _logger.info("Document types imported - Created: %d, Updated: %d, Deactivated: %d", 
                        created_count, updated_count, deactivated_count)
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'document.type.import.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'show_result': True}
            }
            
        except Exception as e:
            _logger.error("Error importing document types: %s", str(e))
            raise UserError(_("Error importing CSV file: %s") % str(e))

    def action_close(self):
        """Close the wizard"""
        return {'type': 'ir.actions.act_window_close'}