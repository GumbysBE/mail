# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.mail.tests.common import MailCase


@tagged("post_install", "-at_install")
class TestMailCcBccRegressions(TransactionCase, MailCase):
    """Every recipient gets exactly one email and a sent notification"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.record = cls.env["res.partner"].create(
            {"name": "Document", "email": "document@example.com"}
        )
        Partner = cls.env["res.partner"]
        cls.johny = Partner.create({"name": "Johny", "email": "Johny@example.com"})
        cls.david = Partner.create({"name": "David", "email": "David.V@example.com"})
        cls.larry = Partner.create({"name": "Larry", "email": "Larry@example.com"})

    def _send(self, to, cc=None, bcc=None):
        cc = cc or self.env["res.partner"]
        bcc = bcc or self.env["res.partner"]
        composer = (
            self.env["mail.compose.message"]
            .with_context(
                default_model=self.record._name,
                default_res_ids=self.record.ids,
                default_composition_mode="comment",
                mail_notify_force_send=True,
            )
            .create(
                {
                    "subject": "repro",
                    "body": "<p>Hello</p>",
                    "partner_ids": [Command.set(to.ids)],
                    "partner_cc_ids": [Command.set(cc.ids)],
                    "partner_bcc_ids": [Command.set(bcc.ids)],
                }
            )
        )
        with self.mock_mail_gateway():
            composer._action_send_mail()
        return self.record.message_ids[:1]

    def _report(self, message):
        notifs = sorted(
            (n.res_partner_id.email, n.notification_status, n.failure_type or "")
            for n in message.notification_ids
        )
        envelopes = [e["smtp_to_list"] for e in self.emails]
        return f"\n  notifications: {notifs}\n  RCPT TO per email: {envelopes}"

    def _assert_ok(self, message, partners):
        report = self._report(message)
        self.assertEqual(
            set(message.notification_ids.mapped("notification_status")),
            {"sent"},
            report,
        )
        self.assertEqual(
            sorted(a.lower() for e in self.emails for a in e["smtp_to_list"]),
            sorted(partners.mapped(lambda p: p.email.lower())),
            report,
        )

    def test_cc_with_uppercase_email(self):
        # David's failure used to shift the envelopes: Larry's copy went to her
        message = self._send(self.johny, cc=self.david + self.larry)
        self._assert_ok(message, self.johny + self.david + self.larry)

    def test_bcc_with_uppercase_email(self):
        message = self._send(self.johny, bcc=self.david)
        self._assert_ok(message, self.johny + self.david)

    def test_template_notification(self):
        # message_post_with_source goes through the composer, without Cc / Bcc
        template = self.env["mail.template"].create(
            {
                "name": "Order confirmation",
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "subject": "Order (Ref {{ object.name }})",
                "body_html": "<p>Confirmed</p>",
                "partner_to": str(self.johny.id),
            }
        )
        with self.mock_mail_gateway():
            message = self.record.with_context(
                force_send=True
            ).message_post_with_source(template, subtype_xmlid="mail.mt_comment")
        self.assertEqual(message.message_type, "notification")
        self._assert_ok(message, self.johny)
