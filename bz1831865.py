#!/usr/bin/python3
import boto.s3.connection
import boto
import subprocess
from subprocess import PIPE, Popen
import time
import os
import requests
import wget
import urllib3
from configparser import ConfigParser
parser = ConfigParser()


def cmdline(command):
    process = Popen(
        args=command,
        stdout=PIPE,
        shell=True
    )
    return process.communicate()[0].decode()


def rgwops():

    unique_id = time.strftime("%Y%m%d%H%M%S")
    user = f"operator_{unique_id}"
    disp_name = f"s3 {user}"
    email = f"{user}@example.com"
    access_key = '123451'
    secret_key = '678901'

    # create user , named = operator_unique_id
    admin_create_command = f"""radosgw-admin user create --uid="{user}" --display-name="{disp_name}" \
    --email="{email}" --access_key="{access_key}" --secret="{secret_key}" """
    cmdline(admin_create_command)

    # create bucket named = test_unique_id and upload some objects
    conn = boto.connect_s3(
        aws_access_key_id = access_key,
         aws_secret_access_key = secret_key,
        host = '10.0.102.64',
         port = 8080,
        is_secure=False,               # uncomment if you are not using ssl

        calling_format = boto.s3.connection.OrdinaryCallingFormat(),
        )

    bkt_name = f"test1_{unique_id}"
    bucket = conn.create_bucket(bkt_name)
    bucket = conn.get_bucket(bkt_name)

    #bucket.configure_versioning(versioning=True)
    config = bucket.get_versioning_status()
    print(config)

    for i in range(1, 10):
        creat_name = 'logC_' + str(i)
        print("creating object" + creat_name)
        key = bucket.new_key(creat_name+'/')
        key.set_contents_from_string('hello how are you')

    # install and setup s3cmd for the above user
    print('It will create a file as /root/.s3cfg_{}'.format(user))
    s3cmd_configure = os.system('s3cmd --configure --dump-config > /root/.s3cfg_{}'.format(user))
    print(s3cmd_configure)
    print('Make some changes to .s3cfg file')
    hostname = os.uname()[1]
    port_number = '8080'
    os.system(
        'sed -i -e \'s,^host_base *=.*,host_base = http://{}:{},;s,host_bucket *=.*,host_bucket = http://{}:{},;s, \
        website_endpoint *=.*,website_endpoint = http://%(bucket)s.{}-%(location)s,;s,access_key *=.*,access_key = {},\
        ;s,secret_key *=.*,secret_key = {},;s,use_https *=.*,use_https = False,;s,gpg_command *=.*,gpg_command = /usr/bin/gpg,\
        ;s,progress_meter *=.*,progress_meter = True,;s,proxy_port *=.*,proxy_port = 0,\' /root/.s3cfg_{}'.format(
            hostname, port_number, hostname, port_number, hostname, access_key, secret_key, user))
    s3cmd_work = os.system('s3cmd ls -c /root/.s3cfg_{}'.format(user))
    exit_status = os.system('echo $?')
    if exit_status == 0:
        print("Bucket list above and below")
    else:
        os.system(
            'sed -i -e \'s,^host_base *=.*,host_base = http://{}:80,;s,host_bucket *=.*,host_bucket = http://{}:80,;s, \
            website_endpoint *=.*,website_endpoint = http://%(bucket)s.{}-%(location)s,;s,access_key *=.*,access_key = {},\
            ;s,secret_key *=.*,secret_key = {},;s,use_https *=.*,use_https = False,;s,gpg_command *=.*,gpg_command = /usr/bin/gpg,\
            ;s,progress_meter *=.*,progress_meter = True,;s,proxy_port *=.*,proxy_port = 0,\' /root/.s3cfg_{}'.format(
                hostname, hostname, hostname, access_key, secret_key, user))
    s3cmd_work = os.system('s3cmd ls -c /root/.s3cfg_{}'.format(user))
    print(s3cmd_work)

    # check the acl info of the bucket created
    acl_info_check(bkt_name, user)

    # setacl --public-read
    acl_set = f"s3cmd setacl --acl-public s3://{bkt_name} -c .s3cfg_{user}"
    print(cmdline(acl_set))

    # after setting acl , again check the info
    acl_info_check(bkt_name, user)

    # change the conf file
    ceph_conf_change(hostname)

    # restart the rgw
    restart_rgw = f"systemctl restart ceph-radosgw@rgw.{hostname}.rgw0.service"
    cmdline(restart_rgw)

    # status of rgw
    status_rgw = f"systemctl status ceph-radosgw@rgw.{hostname}.rgw0.service"
    print(cmdline(status_rgw))

    # check the time
    get_time = time.strftime("%H:%M:%S")
    print(get_time)

    # curl url from s3cmd info
    # install package requests

    curl_url = f"curl http://10.0.102.64:8080/{bkt_name}/"
    print(curl_url)

    url = f"http://{hostname}:8080/{bkt_name}/"
    print(url)
    print(type(url))
    # headers = {"content-type": "application/json", "Accept-Charset": "UTF-8"}
    # r = requests.get(url, data={"sample": "data"}, headers=headers)
    # response = requests.get(url)
    # data = r.json()
    # print(data)

    # c1 = os.system('wget {}'.format(url)) - refused
    # c1 = os.system('curl -I {}'.format(url)) - refused
    # print(c1)
    # print(cmdline(curl_url))

    # subprocess.run(['curl', curl_url])

    # install wget
    # filename = wget.download(url) - refused

    # trying urllib3 another techq
    http = urllib3.PoolManager()
    r = http.request('GET', curl_url)
    print(r.status)

    # regx uid+anonymous part search
    str_check = "uid+anonymous"
    grep_file = f"grep -A 200 {get_time} /var/log/ceph/ceph-rgw-{hostname}.rgw0.log | grep {str_check}"
    # print(grep_file)
    print(cmdline(grep_file))

def ceph_conf_change(hostname):
    # set the debug rgw = 20 , debug ms = 1,  in the .rgw0 instance
    file_name = '/etc/ceph/ceph.conf'
    section_name = 'client.rgw.{}.rgw0'.format(hostname)
    parser.read(file_name)
    parser.set(section_name, 'debug ms', '1')
    parser.set(section_name, 'debug rgw', '20')
    with open(file_name, 'w') as f:
        parser.write(f)
    f.close()
    print(parser.get(section_name, 'debug ms'))
    print(parser.get(section_name, 'debug rgw'))



def acl_info_check(bkt_name, user):
    # check the acl info of the bucket created
    acl_check = f"s3cmd info s3://{bkt_name} -c .s3cfg_{user}"
    print(cmdline(acl_check))


if __name__ == '__main__':
    rgwops()

