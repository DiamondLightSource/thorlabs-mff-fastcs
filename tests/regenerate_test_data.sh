# If you changed some code which you expect to change the test reference data, then run
# this script to regenerate it.
#
# NOTE: Examine the git diff carefully to make sure the new test data
# is as you expect them to be

data_path=$(dirname $0)/data/schema.json
thorlabs-mff-fastcs schema > $data_path
