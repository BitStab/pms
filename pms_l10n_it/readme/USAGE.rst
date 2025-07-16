Installation & Quick Start
==========================

Prerequisites
-------------

-  Odoo 16.0
-  PMS (Property Management System) module
-  Python requests library
-  Valid Alloggiati Web credentials

Installation Steps
------------------

1. **Install the module:**

   .. code:: bash

      # Add to addons path and install
      odoo -d your_database -i pms_l10n_it

2. **Configure your property:**

   ::

      PMS > Configuration > Properties > [Your Property] > Italian Guest Registration

3. **Enter Alloggiati Web credentials:**

   -  Username (provided by Questura)
   -  Password
   -  WS Key (generated in Alloggiati Web interface)
   -  Structure Code (Codice Struttura)
   -  Category Code (accommodation type)

4. **Test the connection:** Click “Test Connection” to verify
   credentials

5. **Configure automation:**

   -  Enable automatic registration
   -  Set registration time (default: 23:00)
   -  Configure guest selection criteria
   -  Set exemption rules for minors

Configuration Guide
===================

🏢 Property Configuration
-------------------------

Basic Settings
~~~~~~~~~~~~~~

Navigate to **PMS > Configuration > Properties** and select your
property:

**Authentication Settings:** - **Alloggiati Web URL:** Pre-configured
government endpoint - **Username:** Your Alloggiati Web username (from
Questura) - **Password:** Your current password - **WS Key:** Generated
from Alloggiati Web interface - **Structure Code:** Official code
assigned by Police - **Structure Category:** Type of accommodation
(Hotel, B&B, etc.) - **Test Mode:** Enable for testing without real
transmissions

Automatic Registration
~~~~~~~~~~~~~~~~~~~~~~

Configure automated daily registration:

-  **Auto Register on Check-in:** Enable automatic processing
-  **Registration Time:** Daily processing time (24h format)
-  **Auto-selection Criteria:**

   -  **All Guests:** Register everyone
   -  **Adults Only:** Exclude minors under 18
   -  **Non-exempt:** Exclude already exempted guests
   -  **By Nationality:** Filter by specific countries

-  **Registration Delay:** Wait time after check-in (hours)
-  **Minor Exemption Age:** Automatic exemption threshold (default: 14)

🌐 Remote Check-In Setup
~~~~~~~~~~~~~~~~~~~~~~~~

Enable guest self-service registration:

-  **Enable Remote Check-in:** Allow guests to register online
-  **Available Hours Before:** How early guests can check-in online
   (default: 48h)
-  **Reminder Hours:** When to send reminder emails (default: 24h)
-  **Notification Emails:** Addresses for registration alerts

📧 Notification Settings
~~~~~~~~~~~~~~~~~~~~~~~~

Configure email alerts and summaries:

-  **Success Notifications:** Email confirmations for completed
   registrations
-  **Error Notifications:** Immediate alerts for failed registrations
-  **Weekly Summaries:** Comprehensive reports with statistics
-  **Notification Recipients:** Comma-separated email addresses

.. _remote-check-in-portal-1:

📱 Remote Check-In Portal
=========================

The remote check-in feature allows guests to complete their registration
before arrival, reducing front desk workload and ensuring compliance.

🔗 How It Works
---------------

1. **Automatic Link Generation:**

   -  System generates secure check-in links for upcoming reservations
   -  Links sent via email 48 hours before arrival (configurable)
   -  Reminder emails sent 24 hours before arrival

2. **Guest Experience:**

   -  Guests receive personalized email with secure link
   -  Mobile-friendly registration form
   -  Support for multiple guests in single reservation
   -  Real-time validation and error feedback
   -  Privacy consent management

3. **Required Information:**

   -  Personal details (name, birth date, gender)
   -  Nationality and residence information
   -  Document details (type, number, issue date)
   -  Contact information (optional)
   -  Privacy and marketing consents

4. **Security Features:**

   -  Unique token-based access
   -  Automatic link expiration (7 days default)
   -  Limited access tracking
   -  GDPR-compliant data handling

🎛️ Management Interface
-----------------------

**Token Management:** - View active check-in links - Send manual
reminders - Resend expired links - Monitor completion status

**Guest Data Review:** - Validate submitted information - Complete
registration with authorities - Handle incomplete submissions - Export
for integration with PMS

📊 Dashboard & Monitoring
=========================

The comprehensive dashboard provides real-time insights into
registration performance and compliance status.

📈 Key Metrics
--------------

**Daily Statistics:** - Total guests requiring registration -
Successfully registered guests - Pending registrations - Failed attempts
- Registration success rate - Average processing time

**Guest Analytics:** - Top guest nationalities - Registration patterns
by day/month - Document type distributions - Exemption reason analysis

**Performance Monitoring:** - API response times - Error rate trends -
Peak usage periods - System availability

🚨 Alert System
---------------

Automated monitoring generates alerts for:

-  **High Pending Count:** Too many unregistered guests
-  **Registration Failures:** API errors or data issues
-  **Deadline Approaching:** Same-day arrivals not registered
-  **Connection Issues:** Alloggiati Web service problems

Alert notifications are sent via email to configured recipients with
detailed information and recommended actions.

📄 Receipt & Compliance Management
==================================

🔄 Automatic Receipt Download
-----------------------------

The system automatically downloads receipts from Alloggiati Web:

-  **Schedule:** Every 6 hours
-  **Retention:** Last 30 days (configurable)
-  **Storage:** PDF format with metadata
-  **Verification:** Cross-reference with registration records

**Manual Operations:** - Download specific date ranges - Retry failed
downloads - Export receipts for external storage - Generate compliance
reports

📋 Data Management
==================

🌍 Reference Tables
-------------------

The module maintains up-to-date reference data for accurate
registrations:

**Synchronized Tables:** - **Luoghi (Places):** Countries, regions, and
municipalities - **Tipi Documento:** Valid document types - **Tipi
Alloggiato:** Guest categories by accommodation type - **Lista
Appartamenti:** Apartment management (where applicable)

**Synchronization:** - **Automatic:** Monthly sync via cron job -
**Manual:** On-demand table updates - **CSV Import:** Bulk import from
Alloggiati Web exports

CSV Import Wizard
~~~~~~~~~~~~~~~~~

Import reference data from Alloggiati Web CSV exports:

1. Navigate to **Italian Registration > Configuration > Import CSV
   Tables**
2. Select table type (Places, Documents, Guest Types, etc.)
3. Upload CSV file with proper encoding
4. Preview data and configure import options
5. Execute import with validation

📧 Email Templates & Notifications
==================================

🎨 Customizable Templates
-------------------------

The module includes professional email templates for:

**Remote Check-In:** - Initial invitation with branded design - Reminder
notifications - Completion confirmations - Error notifications

**Registration Alerts:** - Success confirmations with guest details -
Failure alerts with error diagnostics - Weekly summary reports with
analytics - Compliance deadline warnings

**Template Features:** - Responsive HTML design - Multi-language support
- Property branding integration - Dynamic content based on data

.. _advanced-configuration-1:

⚙️ Advanced Configuration
=========================

🔧 System Parameters
--------------------

Fine-tune system behavior through configuration parameters:

**Registration Processing:**

.. code:: python

   # Maximum retry attempts for failed registrations
   pms_l10n_it.max_retries = 3

   # API timeout in seconds
   pms_l10n_it.api_timeout = 90

   # Batch size for bulk processing
   pms_l10n_it.batch_size = 50

**Remote Check-In:**

.. code:: python

   # Token validity period (days)
   pms_l10n_it.token_validity = 7

   # Maximum access attempts
   pms_l10n_it.max_access_attempts = 10

   # Data retention period (days)
   pms_l10n_it.data_retention = 365

🛠️ Troubleshooting
==================

Common Issues and Solutions
---------------------------

❌ Authentication Failed
~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:** “Authentication failed” error messages **Solutions:** 1.
Verify username, password, and WS Key in property settings 2. Check if
credentials are active in Alloggiati Web portal 3. Test connection using
“Test Connection” button 4. Contact Questura if credentials appear
correct

❌ Invalid Schedina Format
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:** “Invalid format” or “Data validation failed”
**Solutions:** 1. Check guest data completeness (all required fields) 2.
Verify document numbers and dates 3. Ensure nationality and residence
information is accurate 4. Use “Validate Guest Data” option in property
settings

❌ Connection Timeout
~~~~~~~~~~~~~~~~~~~~~

**Symptoms:** “Request timeout” or “Network error” **Solutions:** 1.
Check internet connectivity 2. Verify Alloggiati Web service status 3.
Increase timeout setting in system parameters 4. Retry during off-peak
hours

❌ Remote Check-In Not Working
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:** Guests cannot access check-in form **Solutions:** 1.
Verify remote check-in is enabled for property 2. Check if token has
expired 3. Confirm email delivery (check spam folders) 4. Test with
different browsers/devices

📊 Performance Optimization
===========================

For high-volume properties:

**Database Optimization:** - Regular cleanup of old registration data -
Index optimization for search queries - Archive old receipts to external
storage

**API Usage:** - Batch registration for multiple guests - Implement
queuing for peak periods - Monitor API rate limits

**Monitoring:** - Enable debug logging for troubleshooting - Set up
external monitoring for critical alerts - Regular backup of registration
data

🔒 Security & Privacy
=====================

Data Protection
---------------

The module implements comprehensive security measures:

**Data Encryption:** - HTTPS for all API communications - Encrypted
storage of sensitive information - Secure token generation for remote
access

**Access Control:** - Role-based permissions for different user types -
Multi-company data isolation - Audit trails for all registration
activities

**GDPR Compliance:** - Explicit consent collection for data processing -
Right to erasure implementation - Data portability support - Privacy
policy integration

🚀 Roadmap & Future Features
============================

Planned Enhancements
--------------------

**Short Term (v2.1):** - [ ] Enhanced mobile app integration - [ ] QR
code check-in support - [ ] Advanced document scanning - [ ] Real-time
sync with PMS reservations

**Medium Term (v2.2):** - [ ] Multi-language guest portal - [ ]
Integration with Italian ISTAT reporting - [ ] Advanced analytics and
forecasting - [ ] API for third-party integrations

**Long Term (v3.0):** - [ ] AI-powered data validation - [ ] Predictive
compliance alerts - [ ] Integration with European registration systems -
[ ] Blockchain-based verification

🤝 Contributing
===============

We welcome contributions to improve this module:

**Development:** - Fork the repository - Create feature branches -
Submit pull requests with tests - Follow OCA development guidelines

**Reporting Issues:** - Use GitHub Issues for bug reports - Provide
detailed reproduction steps - Include relevant log excerpts - Specify
Odoo and module versions

**Documentation:** - Improve user guides - Add translation support -
Create video tutorials - Share best practices

📞 Support & Resources
======================

**Official Documentation:** - `Alloggiati Web
Portal <https://alloggiatiweb.poliziadistato.it/>`__ - `Italian Ministry
of Interior Regulations <https://www.interno.gov.it/>`__ - `OCA PMS
Documentation <https://github.com/OCA/pms>`__

**Community Support:** - `OCA Community
Forum <https://odoo-community.org/>`__ - `GitHub
Discussions <https://github.com/OCA/pms/discussions>`__ - `Odoo Apps
Store <https://apps.odoo.com/>`__

**Professional Support:** - Contact module maintainers for commercial
support - Certified Odoo partners for implementation - Custom
development services available

📜 Legal Information
====================

**Compliance Notice:** This module is designed to facilitate compliance
with Italian law requirements for tourist accommodation guest
registration. Users remain responsible for ensuring proper configuration
and usage in accordance with current regulations.

**Disclaimer:** While this module implements current legal requirements,
regulations may change. Users should regularly verify compliance with
current Italian law and update the module accordingly.

**License:** This module is licensed under AGPL-3. See LICENSE file for
details.

--------------

**Credits**

Authors ~~~~~~~ \* IT-Stecher

Contributors ~~~~~~~~~~~~ \* Bitstab \* Additional contributors welcome