from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.clean import cleanup 
import time

def build_realistic_large_topology():
    setLogLevel('info')

    # info('*** 0. Cleaning up old Mininet interfaces...\n')
    # cleanup()

    # استخدام TCLink لإضافة خصائص التأخير والسعة للوصلات
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch, link=TCLink)

    info('*** 1. Connecting to Remote Ryu Controller...\n')
    #  التعديل الأساسي: تغيير المنفذ إلى 6653 بدلاً من 8080
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    info('*** 2. Building Realistic Multi-Tier Network Topology...\n')
    
    # Switches
    core_s1 = net.addSwitch('s1', protocols='OpenFlow13')
    acc_s2 = net.addSwitch('s2', protocols='OpenFlow13')
    acc_s3 = net.addSwitch('s3', protocols='OpenFlow13')

    info('*** 3. Creating Hosts with Fixed MAC Addresses...\n')
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
    h4 = net.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
    h5 = net.addHost('h5', ip='10.0.0.5/24', mac='00:00:00:00:00:05')
    
    server = net.addHost('server', ip='10.0.0.100/24', mac='00:00:00:00:00:fe')

    info('*** 4. Connecting Links with Constraints...\n')
    net.addLink(core_s1, acc_s2, bw=100, delay='2ms')
    net.addLink(core_s1, acc_s3, bw=100, delay='2ms')

    net.addLink(h1, acc_s2, bw=10, delay='5ms')
    net.addLink(h2, acc_s2, bw=10, delay='5ms')
    net.addLink(h3, acc_s2, bw=10, delay='5ms')

    net.addLink(h4, acc_s3, bw=10, delay='10ms')
    net.addLink(h5, acc_s3, bw=10, delay='10ms')
    net.addLink(server, core_s1, bw=50, delay='1ms')

    info('*** 5. Starting Network...\n')
    net.start()

    info('*** 6. Generating Real Background Traffic...\n')
    server.cmd('python3 -m http.server 80 &')
    server.cmd('iperf -s -u &')

    time.sleep(2)

    # تشغيل حركة البيانات
    h1.cmd('while true; do curl -s http://10.0.0.100 > /dev/null; sleep 2; done &')
    h2.cmd('while true; do curl -s http://10.0.0.100 > /dev/null; sleep 1; done &')
    h4.cmd('iperf -c 10.0.0.100 -u -b 8M -t 99999 &')
    h3.cmd('ping 10.0.0.100 -i 0.5 > /dev/null &')

    info('\n*** Topology Built Successfully! Entering CLI...\n')
    CLI(net)

    info('*** Cleaning background processes...\n')
    server.cmd('killall python3 iperf curl')
    net.stop()

if __name__ == '__main__':
    build_realistic_large_topology()
    