#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.firewall import find_nftables_rule
from vyos.utils.process import cmd
from vyos.utils.file import read_file

base_path = ['system', 'conntrack']

def get_sysctl(parameter):
    tmp = parameter.replace(r'.', r'/')
    return read_file(f'/proc/sys/{tmp}')

class TestSystemConntrack(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemConntrack, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def verify_nftables(self, nftables_search, table, inverse=False, args=''):
        nftables_output = cmd(f'sudo nft {args} list table {table}')

        for search in nftables_search:
            matched = False
            for line in nftables_output.split("\n"):
                if all(item in line for item in search):
                    matched = True
                    break
            self.assertTrue(not matched if inverse else matched, msg=search)

    def test_conntrack_options(self):
        conntrack_config = {
            'net.netfilter.nf_conntrack_expect_max' : {
                'cli'           : ['expect-table-size'],
                'test_value'    : '8192',
                'default_value' : '2048',
            },
            'net.nf_conntrack_max' :{
                'cli'           : ['table-size'],
                'test_value'    : '500000',
                'default_value' : '262144',
            },
            'net.ipv4.tcp_max_syn_backlog' :{
                'cli'           : ['tcp', 'half-open-connections'],
                'test_value'    : '2048',
                'default_value' : '512',
            },
            'net.netfilter.nf_conntrack_tcp_loose' :{
                'cli'           : ['tcp', 'loose'],
                'test_value'    : 'disable',
                'default_value' : '1',
            },
            'net.netfilter.nf_conntrack_tcp_max_retrans' :{
                'cli'           : ['tcp', 'max-retrans'],
                'test_value'    : '128',
                'default_value' : '3',
            },
            'net.netfilter.nf_conntrack_icmp_timeout' :{
                'cli'           : ['timeout', 'icmp'],
                'test_value'    : '180',
                'default_value' : '30',
            },
            'net.netfilter.nf_conntrack_generic_timeout' :{
                'cli'           : ['timeout', 'other'],
                'test_value'    : '1200',
                'default_value' : '600',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_close_wait' :{
                'cli'           : ['timeout', 'tcp', 'close-wait'],
                'test_value'    : '30',
                'default_value' : '60',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_close' :{
                'cli'           : ['timeout', 'tcp', 'close'],
                'test_value'    : '20',
                'default_value' : '10',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_established' :{
                'cli'           : ['timeout', 'tcp', 'established'],
                'test_value'    : '1000',
                'default_value' : '432000',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_fin_wait' :{
                'cli'           : ['timeout', 'tcp', 'fin-wait'],
                'test_value'    : '240',
                'default_value' : '120',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_last_ack' :{
                'cli'           : ['timeout', 'tcp', 'last-ack'],
                'test_value'    : '300',
                'default_value' : '30',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_syn_recv' :{
                'cli'           : ['timeout', 'tcp', 'syn-recv'],
                'test_value'    : '100',
                'default_value' : '60',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_syn_sent' :{
                'cli'           : ['timeout', 'tcp', 'syn-sent'],
                'test_value'    : '300',
                'default_value' : '120',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_time_wait' :{
                'cli'           : ['timeout', 'tcp', 'time-wait'],
                'test_value'    : '303',
                'default_value' : '120',
            },
            'net.netfilter.nf_conntrack_udp_timeout' :{
                'cli'           : ['timeout', 'udp', 'other'],
                'test_value'    : '90',
                'default_value' : '30',
            },
            'net.netfilter.nf_conntrack_udp_timeout_stream' :{
                'cli'           : ['timeout', 'udp', 'stream'],
                'test_value'    : '200',
                'default_value' : '180',
            },
        }

        for parameter, parameter_config in conntrack_config.items():
            self.cli_set(base_path + parameter_config['cli'] + [parameter_config['test_value']])

        # commit changes
        self.cli_commit()

        # validate configuration
        for parameter, parameter_config in conntrack_config.items():
            tmp = parameter_config['test_value']
            # net.netfilter.nf_conntrack_tcp_loose has a fancy "disable" value,
            # make this work
            if tmp == 'disable':
                tmp = '0'
            self.assertEqual(get_sysctl(f'{parameter}'), tmp)

        # delete all configuration options and revert back to defaults
        self.cli_delete(base_path)
        self.cli_commit()

        # validate configuration
        for parameter, parameter_config in conntrack_config.items():
            self.assertEqual(get_sysctl(f'{parameter}'), parameter_config['default_value'])


    def test_conntrack_module_enable(self):
        # conntrack helper modules are disabled by default
        modules = {
            'ftp': {
                'driver': ['nf_nat_ftp', 'nf_conntrack_ftp'],
                'nftables': ['ct helper set "ftp_tcp"']
            },
            'h323': {
                'driver': ['nf_nat_h323', 'nf_conntrack_h323'],
                'nftables': ['ct helper set "ras_udp"',
                             'ct helper set "q931_tcp"']
            },
            'nfs': {
                'nftables': ['ct helper set "rpc_tcp"',
                             'ct helper set "rpc_udp"']
            },
            'pptp': {
                'driver': ['nf_nat_pptp', 'nf_conntrack_pptp'],
                'nftables': ['ct helper set "pptp_tcp"']
             },
            'sip': {
                'driver': ['nf_nat_sip', 'nf_conntrack_sip'],
                'nftables': ['ct helper set "sip_tcp"',
                             'ct helper set "sip_udp"']
             },
            'sqlnet': {
                'nftables': ['ct helper set "tns_tcp"']
            },
            'tftp': {
                'driver': ['nf_nat_tftp', 'nf_conntrack_tftp'],
                'nftables': ['ct helper set "tftp_udp"']
             },
        }

        # load modules
        for module in modules:
            self.cli_set(base_path + ['modules', module])

        # commit changes
        self.cli_commit()

        # verify modules are loaded on the system
        for module, module_options in modules.items():
            if 'driver' in module_options:
                for driver in module_options['driver']:
                    self.assertTrue(os.path.isdir(f'/sys/module/{driver}'))
            if 'nftables' in module_options:
                for rule in module_options['nftables']:
                    self.assertTrue(find_nftables_rule('ip vyos_conntrack', 'VYOS_CT_HELPER', [rule]) != None)

        # unload modules
        for module in modules:
            self.cli_delete(base_path + ['modules', module])

        # commit changes
        self.cli_commit()

        # verify modules are not loaded on the system
        for module, module_options in modules.items():
            if 'driver' in module_options:
                for driver in module_options['driver']:
                    self.assertFalse(os.path.isdir(f'/sys/module/{driver}'))
            if 'nftables' in module_options:
                for rule in module_options['nftables']:
                    self.assertTrue(find_nftables_rule('ip vyos_conntrack', 'VYOS_CT_HELPER', [rule]) == None)

    def test_conntrack_hash_size(self):
        hash_size = '65536'
        hash_size_default = '32768'

        self.cli_set(base_path + ['hash-size', hash_size])

        # commit changes
        self.cli_commit()

        # verify new configuration - only effective after reboot, but
        # a valid config file is sufficient
        tmp = read_file('/etc/modprobe.d/vyatta_nf_conntrack.conf')
        self.assertIn(hash_size, tmp)

        # Test default value by deleting the configuration
        self.cli_delete(base_path + ['hash-size'])

        # commit changes
        self.cli_commit()

        # verify new configuration - only effective after reboot, but
        # a valid config file is sufficient
        tmp = read_file('/etc/modprobe.d/vyatta_nf_conntrack.conf')
        self.assertIn(hash_size_default, tmp)

    def test_conntrack_ignore(self):
        address_group = 'conntracktest'
        address_group_member = '192.168.0.1'
        ipv6_address_group = 'conntracktest6'
        ipv6_address_group_member = 'dead:beef::1'

        self.cli_set(['firewall', 'group', 'address-group', address_group, 'address', address_group_member])
        self.cli_set(['firewall', 'group', 'ipv6-address-group', ipv6_address_group, 'address', ipv6_address_group_member])

        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'source', 'address', '192.0.2.1'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'destination', 'address', '192.0.2.2'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'destination', 'port', '22'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'protocol', 'tcp'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'tcp', 'flags', 'syn'])

        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '2', 'source', 'address', '192.0.2.1'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '2', 'destination', 'group', 'address-group', address_group])

        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '11', 'source', 'address', 'fe80::1'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '11', 'destination', 'address', 'fe80::2'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '11', 'destination', 'port', '22'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '11', 'protocol', 'tcp'])

        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '12', 'source', 'address', 'fe80::1'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '12', 'destination', 'group', 'address-group', ipv6_address_group])

        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '13', 'source', 'address', 'fe80::1'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '13', 'destination', 'address', '!fe80::3'])

        self.cli_commit()

        nftables_search = [
            ['ip saddr 192.0.2.1', 'ip daddr 192.0.2.2', 'tcp dport 22', 'tcp flags & syn == syn', 'notrack'],
            ['ip saddr 192.0.2.1', 'ip daddr @A_conntracktest', 'notrack']
        ]

        nftables6_search = [
            ['ip6 saddr fe80::1', 'ip6 daddr fe80::2', 'tcp dport 22', 'notrack'],
            ['ip6 saddr fe80::1', 'ip6 daddr @A6_conntracktest6', 'notrack'],
            ['ip6 saddr fe80::1', 'ip6 daddr != fe80::3', 'notrack']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_conntrack')
        self.verify_nftables(nftables6_search, 'ip6 vyos_conntrack')

        self.cli_delete(['firewall'])

    def test_conntrack_timeout_custom(self):

        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'source', 'address', '192.0.2.1'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'destination', 'address', '192.0.2.2'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'destination', 'port', '22'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'protocol', 'tcp', 'syn-sent', '77'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'protocol', 'tcp', 'close', '88'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'protocol', 'tcp', 'established', '99'])

        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '2', 'inbound-interface', 'eth1'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '2', 'source', 'address', '198.51.100.1'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '2', 'protocol', 'udp', 'unreplied', '55'])

        self.cli_set(base_path + ['timeout', 'custom', 'ipv6', 'rule', '1', 'source', 'address', '2001:db8::1'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv6', 'rule', '1', 'inbound-interface', 'eth2'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv6', 'rule', '1', 'protocol', 'tcp', 'time-wait', '22'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv6', 'rule', '1', 'protocol', 'tcp', 'last-ack', '33'])

        self.cli_commit()

        nftables_search = [
            ['ct timeout ct-timeout-1 {'],
            ['protocol tcp'],
            ['policy = { syn_sent : 1m17s, established : 1m39s, close : 1m28s }'],
            ['ct timeout ct-timeout-2 {'],
            ['protocol udp'],
            ['policy = { unreplied : 55s }'],
            ['chain VYOS_CT_TIMEOUT {'],
            ['ip saddr 192.0.2.1', 'ip daddr 192.0.2.2', 'tcp dport 22', 'ct timeout set "ct-timeout-1"'],
            ['iifname "eth1"', 'meta l4proto udp', 'ip saddr 198.51.100.1', 'ct timeout set "ct-timeout-2"']
        ]

        nftables6_search = [
            ['ct timeout ct-timeout-1 {'],
            ['protocol tcp'],
            ['policy = { last_ack : 33s, time_wait : 22s }'],
            ['chain VYOS_CT_TIMEOUT {'],
            ['iifname "eth2"', 'meta l4proto tcp', 'ip6 saddr 2001:db8::1', 'ct timeout set "ct-timeout-1"']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_conntrack')
        self.verify_nftables(nftables6_search, 'ip6 vyos_conntrack')

        self.cli_delete(['firewall'])
if __name__ == '__main__':
    unittest.main(verbosity=2)
