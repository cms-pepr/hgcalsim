#!/usr/bin/env bash

# wrapper script to ensure that the job script is executed in a bash

echo "running cern htcondor job wrapper"


#
# PATH fix
#

export PATH="{{hgc_env_path}}"


#
# custom proxy handling
#

export X509_USER_PROXY="/tmp/x509up_u$( id -u )"
cp "$( ls -q x509up_u*_* | head -n 1 )" "$X509_USER_PROXY"


#
# run the job file
#

bash "{{job_file}}" $@
