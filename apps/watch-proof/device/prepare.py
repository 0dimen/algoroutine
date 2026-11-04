"""Create an expiring local-device profile OUTSIDE the checkout. Never print credentials."""
import argparse,base64,ipaddress,json,os,pathlib,secrets,subprocess

def prepare(host,destination):
    address=ipaddress.ip_address(host)
    if address.version!=4 or not any(address in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','127.0.0.0/8')):
        raise ValueError('Use a private LAN IPv4 address or loopback')
    dest=pathlib.Path(destination).resolve()
    repo=pathlib.Path(__file__).resolve().parents[3]
    if dest==repo or repo in dest.parents:raise ValueError('Profile must be outside the repository')
    dest.mkdir(mode=0o700,parents=True,exist_ok=False)
    os.chmod(dest,0o700)
    config=dest/'openssl.cnf'
    config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=AlgoRoutine local device\n[ext]\nsubjectAltName=IP:'+host+',IP:127.0.0.1\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,digitalSignature,keyEncipherment,keyCertSign\nextendedKeyUsage=serverAuth\n')
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','7','-config',str(config),'-keyout',str(dest/'key.pem'),'-out',str(dest/'cert.pem')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    der=subprocess.check_output(['openssl','x509','-in',str(dest/'cert.pem'),'-outform','DER'])
    client={'host':host,'port':8792,'token':secrets.token_hex(32),'certificate':base64.b64encode(der).decode()}
    (dest/'client.json').write_text(json.dumps(client))
    (dest/'device.xcconfig').write_text('\n'.join('ROUTINE_SERVER_'+key.upper()+' = '+str(value) for key,value in client.items())+'\n')
    for f in dest.iterdir():os.chmod(f,0o600)
    print('Created private 7-day device profile at '+str(dest))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--output',required=True);a=p.parse_args();prepare(a.host,a.output)
