import json
from threading import Event
import unittest
from unittest.mock import patch

from ultimate2c_ring import device, reporting
from ultimate2c_ring.controller import Operations
from ultimate2c_ring.gui import diagnostics


class DesktopSafety(unittest.TestCase):
    def test_one_operation_and_declining_pending_confirmation(self):
        operations=Operations()
        entered=Event()
        def action():
            entered.set()
            return operations.confirm({'target_profile':'off'})
        operations.start('apply',action)
        self.assertTrue(entered.wait(2))
        kind,pending=operations.events.get(timeout=2)
        self.assertEqual(kind,'confirm')
        with self.assertRaises(RuntimeError): operations.start('check',lambda:None)
        operations.decline_pending()
        operations.thread.join(2)
        self.assertFalse(operations.thread.is_alive())
        kind,result=operations.events.get_nowait()
        self.assertEqual((kind,result['value']),('result',False))
        self.assertFalse(operations.running)
        self.assertFalse(operations.thread.daemon)

    def test_error_still_releases_worker_for_next_operation(self):
        operations=Operations()
        def broken(): raise OSError('Disconnected')
        operations.start('check',broken)
        operations.thread.join(2)
        self.assertFalse(operations.running)
        events=[]
        while not operations.events.empty(): events.append(operations.events.get_nowait())
        self.assertEqual([kind for kind,value in events],['error','finished'])
        operations.start('check',lambda:42)
        operations.thread.join(2)
        self.assertEqual(operations.events.get_nowait()[1]['value'],42)

    def test_observer_failure_cannot_interrupt_operation_and_is_scoped(self):
        def broken(kind,values): raise OSError('Display unavailable')
        with reporting.observe(broken):
            reporting.message('Continue verifying')
            reporting.progress('Rollback',50)
        self.assertIsNone(reporting._observer.get())

    def test_report_excludes_paths_dumps_serials_and_raw_errors(self):
        status={'model':'Ultimate 2C Wireless','compatible':True,'profile':'dim',
                'application_sha256':'a'*64,'path':'private-usb-path','serial_number':'secret-serial',
                'backup_folder':'private-folder','memory':b'private-dump'}
        report=json.dumps(diagnostics(status,'OSError'))
        for secret in ('private-usb-path','secret-serial','private-folder','private-dump'):
            self.assertNotIn(secret,report)
        self.assertIn('application_sha256',report)

    def test_receiver_only_has_actionable_message(self):
        class Hid:
            def enumerate(self,vid,pid):
                return [{'product_id':0x301C,'usage_page':0xFFA0,'interface_number':0}]
        with patch.object(device,'hid_module',return_value=Hid()):
            with self.assertRaisesRegex(RuntimeError,'Only the USB receiver'):
                device.discover()


if __name__=='__main__': unittest.main()
