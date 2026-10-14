# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import ast

from odoo import models

from .mail_mail import format_emails_str


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    # ------------------------------------------------------------
    # MAIL.MESSAGE HELPERS
    # ------------------------------------------------------------

    def _get_message_create_valid_field_names(self):
        """Let ``message_post`` store the Cc / Bcc partners on the message.

        Odoo drops any value given to ``message_post`` that is not listed here.
        """
        field_names = super()._get_message_create_valid_field_names()
        field_names.update({"recipient_cc_ids", "recipient_bcc_ids"})
        return field_names

    # ------------------------------------------------------
    # NOTIFICATION API
    # ------------------------------------------------------

    def _notify_by_email_get_base_mail_values(
        self, message, recipients_data, additional_values=None
    ):
        """Mark the emails of a message with Cc / Bcc, and keep those
        recipients out of Reply-All."""
        res = super()._notify_by_email_get_base_mail_values(
            message, recipients_data, additional_values=additional_values
        )
        # No flagged recipient means no Cc / Bcc: spares reading the message
        if not any(data.get("is_cc_bcc") for data in recipients_data):
            return res
        _partners_to, partners_cc, partners_bcc = message._get_cc_bcc_audience()
        if not partners_cc and not partners_bcc:
            return res
        # Shown on the email, and the sign for mail.mail that its copies need
        # the Cc / Bcc headers, also when sent later by the queue or Retry
        if partners_cc:
            res["email_cc"] = format_emails_str(partners_cc)
        if partners_bcc:
            res["email_bcc"] = format_emails_str(partners_bcc)
        # Odoo lists every external recipient in this header and merges it into
        # To at sending: the Cc and Bcc would end up in everyone's To
        if res.get("headers"):
            headers = ast.literal_eval(res["headers"])
            headers.pop("X-Msg-To-Add", None)
            res["headers"] = repr(headers)
        return res

    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        """Add the Cc / Bcc partners of the message to the email recipients."""
        recipients_data = super()._notify_get_recipients(
            message, msg_vals=msg_vals, **kwargs
        )
        # msg_vals are the values the message was just created with: checking
        # them instead of the message spares two queries on every message
        if msg_vals and not (
            msg_vals.get("recipient_cc_ids") or msg_vals.get("recipient_bcc_ids")
        ):
            return recipients_data
        message_sudo = message.sudo()
        partners_cc_bcc = message_sudo.recipient_cc_ids | message_sudo.recipient_bcc_ids
        if not partners_cc_bcc:
            return recipients_data

        # An explicit Cc / Bcc asks for an email, even to an internal user who
        # chose to handle notifications in Odoo. The flag tells the next steps
        # that this message has Cc / Bcc.
        for data in recipients_data:
            if data["id"] in partners_cc_bcc.ids:
                data.update(notif="email", is_cc_bcc=True)
        # Cc / Bcc partners who do not follow the document: built like Odoo
        # builds followers, so they are grouped by language and notification
        # group like any other recipient
        missing = partners_cc_bcc.filtered(
            lambda p: p.id not in {data["id"] for data in recipients_data}
        )
        if missing:
            msg_vals = msg_vals or {}
            missing_data = self.env["mail.followers"]._get_recipient_data(
                None,
                msg_vals.get("message_type") or message_sudo.message_type,
                msg_vals.get("subtype_id") or message_sudo.subtype_id.id,
                missing.ids,
            )[0]
            recipients_data += [
                {**data, "notif": "email", "is_cc_bcc": True}
                for data in missing_data.values()
                if data["active"]
            ]
        return recipients_data
