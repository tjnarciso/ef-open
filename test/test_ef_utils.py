"""
Copyright 2016-2017 Ellation, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from StringIO import StringIO
import subprocess
import unittest
import urllib2

from mock import Mock, patch
import botocore.exceptions

# For local application imports, context must be first despite lexicon ordering
import context
from src.ef_utils import create_aws_clients, env_valid, fail, get_account_alias, get_env_short, global_env_valid, \
  get_instance_aws_context, http_get_instance_env, http_get_instance_role, http_get_metadata, pull_repo, whereami


class TestEFUtils(unittest.TestCase):
  """
  Tests for 'ef_utils.py' Relies on the ef_site_config.py for testing. Look inside that file for where
  some of the test values are coming from.
  """
  @patch('sys.stderr', new_callable=StringIO)
  def test_fail_with_message(self, mock_stderr):
    """
    Tests fail() with a regular string message and checks if the message in stderr and exit code matches
    :param mock_stderr: StringIO
    :return: None
    """
    with self.assertRaises(SystemExit) as exception:
      fail("Error Message")
    error_message = mock_stderr.getvalue().strip()
    self.assertEquals(error_message, "Error Message")
    self.assertEquals(exception.exception.code, 1)

  @patch('sys.stdout', new_callable=StringIO)
  @patch('sys.stderr', new_callable=StringIO)
  def test_fail_with_message_and_exception_data(self, mock_stderr, mock_stdout):
    """
    Test fail() with a regular string message and a python object as the exception data
    :param mock_stderr: StringIO
    :param mock_stdout: StringIO
    :return: None
    """
    with self.assertRaises(SystemExit) as exception:
      fail("Error Message", {"ErrorCode": 22})
    error_message = mock_stderr.getvalue().strip()
    self.assertEquals(error_message, "Error Message")
    self.assertEquals(exception.exception.code, 1)
    output_message = mock_stdout.getvalue().strip()
    self.assertEquals(output_message, "{'ErrorCode': 22}")

  @patch('sys.stderr', new_callable=StringIO)
  def test_fail_with_None_message(self, mock_stderr):
    """
    Test fail() with a None object
    :param mock_stderr: StringIO
    :return: None
    """
    with self.assertRaises(SystemExit) as exception:
      fail(None)
    error_message = mock_stderr.getvalue().strip()
    self.assertEquals(error_message, "None")
    self.assertEquals(exception.exception.code, 1)

  @patch('urllib2.urlopen')
  def test_http_get_metadata_200_status_code(self, mock_urllib2):
    """
    Test http_get_metadata with mock urllib2.urlopen call that returns 200 and ami ID
    :param mock_urllib2: MagicMock
    :return: None
    """
    mock_response = Mock(name="Always 200 Status Code")
    mock_response.getcode.return_value = 200
    mock_response.read.return_value = "ami-12345678"
    mock_urllib2.return_value = mock_response
    response = http_get_metadata("ami-id")
    self.assertEquals(response, "ami-12345678")

  @patch('urllib2.urlopen')
  def test_http_get_metadata_non_200_status_code(self, mock_urllib2):
    """
    Test http_get_metadata with mock urllib2.urlopen call that returns 400.
    :param mock_urllib2: MagicMock
    :return: None
    """
    mock_response = Mock(name="Always non-200 Status Code")
    mock_response.getcode.return_value = 400
    mock_urllib2.return_value = mock_response
    with self.assertRaises(IOError) as exception:
      http_get_metadata("ami-id")
    self.assertTrue("400" in exception.exception.message)
    self.assertTrue("ami-id" in exception.exception.message)

  @patch('urllib2.urlopen')
  def test_http_get_metadata_urllib2_URLError(self, mock_urllib2):
    """
    Test http_get_metadata with mock urllib2.urlopen that raises a URLError exception
    :param mock_urllib2: MagicMock
    :return: None
    """
    mock_urllib2.side_effect = urllib2.URLError("Mock URLError")
    with self.assertRaises(IOError) as exception:
      http_get_metadata("ami-id")
    self.assertTrue("Mock URLError" in exception.exception.message)

  @unittest.skipIf(whereami() == "ec2", "Test is running in ec2 environment, will not fail so must skip.")
  def test_http_get_metadata_urllib2_default_timeout(self):
    with self.assertRaises(IOError) as exception:
      http_get_metadata("ami-id")
    #TODO: A different exception occurs where it says host is down. Need to figure out a different way to check this
    #self.assertTrue("timed out" in exception.exception.message)

  @unittest.skipIf(whereami() == "ec2", "Test is running in ec2 environment, will not fail so must skip.")
  def test_http_get_metadata_urllib2_1_second_timeout(self):
    with self.assertRaises(IOError) as exception:
      http_get_metadata("ami-id", 1)
    # TODO: A different exception occurs where it says host is down. Need to figure out a different way to check this
    #self.assertTrue("timed out" in exception.exception.message)

  @patch('src.ef_utils.http_get_metadata')
  def test_whereami_ec2(self, mock_http_get_metadata):
    mock_http_get_metadata.return_value = "i-123456"
    result = whereami()
    self.assertEquals(result, "ec2")

  @patch('subprocess.check_output')
  @patch('src.ef_utils.access')
  @patch('src.ef_utils.isfile')
  @patch('src.ef_utils.http_get_metadata')
  def test_whereami_virtualbox(self, mock_http_get_metadata, mock_isfile, mock_access, mock_check_output):
    mock_http_get_metadata.return_value = "not ec2"
    mock_isfile.return_value = True
    mock_access.return_value = True
    mock_check_output.return_value = "virtualbox\nkvm\nother\n"
    result = whereami()
    self.assertEquals(result, "virtualbox-kvm")

  @patch('src.ef_utils.gethostname')
  def test_whereami_local(self, mock_gethostname):
    mock_gethostname.return_value = ".local"
    result = whereami()
    self.assertEquals(result, "local")

  @patch('src.ef_utils.gethostname')
  def test_whereami_unknown(self, mock_gethostname):
    mock_gethostname.return_value = "not local"
    result = whereami()
    self.assertEquals(result, "unknown")

  @patch('src.ef_utils.http_get_metadata')
  def test_http_get_instance_env(self, mock_http_get_metadata):
    mock_http_get_metadata.return_value = "{\"InstanceProfileArn\": \"arn:aws:iam::1234:role/dev-server\"}"
    env = http_get_instance_env()
    self.assertEquals(env, "dev")

  @patch('src.ef_utils.http_get_metadata')
  def test_http_get_instance_env_exception(self, mock_http_get_metadata):
    mock_http_get_metadata.return_value = "No data"
    with self.assertRaises(Exception) as exception:
      http_get_instance_env()

  @patch('src.ef_utils.http_get_metadata')
  def test_http_get_instance_role(self, mock_http_get_metadata):
    mock_http_get_metadata.return_value = "{\"InstanceProfileArn\": \"arn:aws:iam::1234:role/dev-server\"}"
    role = http_get_instance_role()
    self.assertEquals(role, "server")

  @patch('src.ef_utils.http_get_metadata')
  def test_http_get_instance_role_exception(self, mock_http_get_metadata):
    mock_http_get_metadata.return_value = "No data"
    with self.assertRaises(Exception) as exception:
      http_get_instance_role()

  @patch('src.ef_utils.http_get_metadata')
  def test_get_instance_aws_context(self, mock_http_get_metadata):
    mock_http_get_metadata.side_effect = ["us-west-2a", "i-00001111f"]
    mock_ec2_client = Mock(name="mock-ec2-client")
    mock_ec2_client.describe_instances.return_value = \
      {
        "Reservations": [
          {
            "OwnerId": "4444",
            "Instances": [
              {
                "IamInstanceProfile": {
                  "Arn": "arn:aws:iam::1234:instance-profile/dev0-server-ftp"
                }
              }
            ]
          }
        ]
      }
    result = get_instance_aws_context(mock_ec2_client)
    self.assertEquals(result["account"], "4444")
    self.assertEquals(result["env"], "dev0")
    self.assertEquals(result["env_short"], "dev")
    self.assertEquals(result["instance_id"], "i-00001111f")
    self.assertEquals(result["region"], "us-west-2")
    self.assertEquals(result["role"], "dev0-server-ftp")
    self.assertEquals(result["service"], "server-ftp")

  @patch('src.ef_utils.http_get_metadata')
  def test_get_instance_aws_context_metadata_exception(self, mock_http_get_metadata):
    mock_http_get_metadata.side_effect = IOError("No data")
    mock_ec2_client = Mock(name="mock-ec2-client")
    with self.assertRaises(IOError) as exception:
      get_instance_aws_context(mock_ec2_client)

  @patch('src.ef_utils.http_get_metadata')
  def test_get_instance_aws_context_ec2_client_exception(self, mock_http_get_metadata):
    mock_http_get_metadata.side_effect = ["us-west-2a", "i-00001111f"]
    mock_ec2_client = Mock(name="mock-ec2-client")
    mock_ec2_client.describe_instances.side_effect = Exception("No instance data")
    with self.assertRaises(Exception) as exception:
      get_instance_aws_context(mock_ec2_client)

  @patch('src.ef_utils.http_get_metadata')
  def test_get_instance_aws_context_ec2_invalid_environment_exception(self, mock_http_get_metadata):
    mock_http_get_metadata.side_effect = ["us-west-2a", "i-00001111f"]
    mock_ec2_client = Mock(name="mock-ec2-client")
    mock_ec2_client.describe_instances.return_value = \
      {
        "Reservations": [
          {
            "OwnerId": "4444",
            "Instances": [
              {
                "IamInstanceProfile": {
                  "Arn": "arn:aws:iam::1234:instance-profile/invalidenv-server-ftp"
                }
              }
            ]
          }
        ]
      }
    with self.assertRaises(Exception) as exception:
      get_instance_aws_context(mock_ec2_client)

  @patch('subprocess.check_output')
  def test_pull_repo_ssh_credentials(self, mock_check_output):
    mock_check_output.side_effect = [
      "user@github.com:company/fake_repo.git "
      "other_user@github.com:company/fake_repo.git",
      "master"
    ]
    try:
      pull_repo()
    except RuntimeError as exception:
      self.fail("Exception occurred during test_pull_repo_ssh_credentials: " + exception.message)
    self.assertTrue(mock_check_output.call)

  @patch('subprocess.check_output')
  def test_pull_repo_https_credentials(self, mock_check_output):
    mock_check_output.side_effect = [
      "origin\thttps://user@github.com/company/fake_repo.git "
      "(fetch)\norigin\thttps://user@github.com/company/fake_repo.git",
      "master"
    ]
    try:
      pull_repo()
    except RuntimeError as exception:
      self.fail("Exception occurred during test_pull_repo_ssh_credentials: " + exception.message)

  @patch('subprocess.check_output')
  def test_pull_repo_first_git_remote_show_error(self, mock_check_output):
    mock_check_output.side_effect = subprocess.CalledProcessError("Forced Error", 1)
    with self.assertRaises(RuntimeError) as exception:
      pull_repo()

  @patch('subprocess.check_output')
  def test_pull_repo_incorrect_repo(self, mock_check_output):
    mock_check_output.side_effect = [
      "user@github.com:company/wrong_repo.git "
      "other_user@github.com:company/wrong_repo.git"
    ]
    with self.assertRaises(RuntimeError):
      pull_repo()

  @patch('subprocess.check_output')
  def test_pull_repo_exception_checking_branch(self, mock_check_output):
    mock_check_output.side_effect = [
      "user@github.com:company/fake_repo.git "
      "other_user@github.com:company/fake_repo.git",
      subprocess.CalledProcessError("Forced Error", 1)
    ]
    with self.assertRaises(RuntimeError):
      pull_repo()

  @patch('subprocess.check_output')
  def test_pull_repo_incorrect_branch(self, mock_check_output):
    mock_check_output.side_effect = [
      "user@github.com:company/fake_repo.git "
      "other_user@github.com:company/fake_repo.git",
      "wrong_branch"
    ]
    with self.assertRaises(RuntimeError):
      pull_repo()

  @patch('subprocess.check_call')
  @patch('subprocess.check_output')
  def test_pull_repo_git_pull_error(self, mock_check_output, mock_check_call):
    mock_check_output.side_effect = [
      "user@github.com:company/fake_repo.git "
      "other_user@github.com:company/fake_repo.git",
      "master"
    ]
    mock_check_call.side_effect = subprocess.CalledProcessError("Forced Error", 1)
    with self.assertRaises(RuntimeError):
      pull_repo()

  @patch('boto3.Session')
  def test_create_aws_clients(self, mock_session_constructor):
    mock_session = Mock(name="mock-boto3-session")
    mock_session.client.return_value = Mock(name="mock-client")
    mock_session_constructor.return_value = mock_session
    amazon_services = ["acm", "batch", "ec2", "sqs"]
    client_dict = create_aws_clients("us-west-2d", "default", *amazon_services)
    self.assertTrue("acm" in client_dict)
    self.assertTrue("batch" in client_dict)
    self.assertTrue("ec2" in client_dict)
    self.assertTrue("sqs" in client_dict)
    self.assertTrue("SESSION" in client_dict)

  @patch('boto3.Session')
  def test_create_aws_clients_no_profile(self, mock_session_constructor):
    mock_session = Mock(name="mock-boto3-session")
    mock_session.client.return_value = Mock(name="mock-client")
    mock_session_constructor.return_value = mock_session
    amazon_services = ["acm", "batch", "ec2", "sqs"]
    client_dict = create_aws_clients("us-west-2d", None, *amazon_services)
    self.assertTrue("acm" in client_dict)
    self.assertTrue("batch" in client_dict)
    self.assertTrue("ec2" in client_dict)
    self.assertTrue("sqs" in client_dict)
    self.assertTrue("SESSION" in client_dict)

  @patch('boto3.Session')
  def test_create_aws_clients_create_session_boto_core_error(self, mock_session_constructor):
    mock_session_constructor.side_effect = botocore.exceptions.BotoCoreError()
    with self.assertRaises(RuntimeError) as exception:
      create_aws_clients("us-west-2d", None, None)
    mock_session_constructor.assert_called_once_with(region_name="us-west-2d")

  def test_get_account_alias(self):
    """
    Checks if get_account_alias returns the correct account based on valid environments
    :return: None
    """
    self.assertEquals(get_account_alias("test"), "amazon_test_account")
    self.assertEquals(get_account_alias("dev0"), "amazon_dev_account")
    self.assertEquals(get_account_alias("dev1"), "amazon_dev_account")
    self.assertEquals(get_account_alias("staging0"), "amazon_staging_account")
    self.assertEquals(get_account_alias("prod"), "amazon_prod_account")
    self.assertEquals(get_account_alias("global.amazon_global_account"), "amazon_global_account")
    self.assertEquals(get_account_alias("mgmt.amazon_mgmt_account"), "amazon_mgmt_account")
    self.assertEquals(get_account_alias("global.amazon_dev_account"), "amazon_dev_account")

  def test_get_account_alias_invalid_env(self):
    """
    Tests if get_account_alias raises exceptions when given invalid environments
    :return: None
    """
    with self.assertRaises(ValueError) as exception:
      get_account_alias("test0")
    self.assertTrue("unknown env" in exception.exception.message)
    with self.assertRaises(ValueError) as exception:
      get_account_alias("non-existent-env")
    self.assertTrue("unknown env" in exception.exception.message)
    with patch('src.ef_utils.env_valid') as mock_env_valid:
      with self.assertRaises(ValueError) as exception:
        mock_env_valid.return_value = True
        get_account_alias("non-existent-env")
    self.assertTrue("has no entry in ENV_ACCOUNT_MAP" in exception.exception.message)

  def test_get_env_short(self):
    """
    Checks if get_env_short returns the correct environment shortname when given valid environments
    :return: None
    """
    self.assertEquals(get_env_short("test"), "test")
    self.assertEquals(get_env_short("dev0"), "dev")
    self.assertEquals(get_env_short("dev1"), "dev")
    self.assertEquals(get_env_short("staging0"), "staging")
    self.assertEquals(get_env_short("prod"), "prod")
    self.assertEquals(get_env_short("global.amazon_global_account"), "global")
    self.assertEquals(get_env_short("mgmt.amazon_mgmt_account"), "mgmt")
    self.assertEquals(get_env_short("global.amazon_dev_account"), "global")

  def test_get_env_short_invalid_envs(self):
    """
    Tests if get_env_short raises exceptions when given invalid environments
    :return: None
    """
    with self.assertRaises(ValueError) as exception:
      get_env_short("test0")
    self.assertTrue("unknown env" in exception.exception.message)
    with self.assertRaises(ValueError) as exception:
      get_env_short("non-existent-env")
    self.assertTrue("unknown env" in exception.exception.message)

  def test_env_valid(self):
    """
    Checks if env_valid returns true for correctly named environments
    :return: None
    """
    self.assertTrue(env_valid("test"))
    self.assertTrue(env_valid("dev0"))
    self.assertTrue(env_valid("dev1"))
    self.assertTrue(env_valid("dev2"))
    self.assertTrue(env_valid("staging0"))
    self.assertTrue(env_valid("prod"))
    self.assertTrue(env_valid("global"))
    self.assertTrue(env_valid("mgmt"))
    self.assertTrue(env_valid("global.amazon_global_account"))
    self.assertTrue(env_valid("mgmt.amazon_mgmt_account"))
    self.assertTrue(env_valid("global.amazon_dev_account"))

  def test_env_valid_invalid_envs(self):
    """
    Checks if env_valid returns ValueError for incorrectly name environments
    :return: None
    """
    with self.assertRaises(ValueError):
      env_valid("test0")
    with self.assertRaises(ValueError):
      env_valid("dev")
    with self.assertRaises(ValueError):
      env_valid("staging")
    with self.assertRaises(ValueError):
      env_valid("prod0")
    with self.assertRaises(ValueError):
      env_valid("invalid_env")

  def test_global_env_valid(self):
    """
    Checks global_env_valid returns true for account scoped envs.
    :return: None
    """
    self.assertTrue(global_env_valid("global"))
    self.assertTrue(global_env_valid("mgmt"))

  def test_global_env_valid_non_scoped_envs(self):
    """
    Checks global_env_valid returns false for non account scoped envs.
    :return: None
    """
    with self.assertRaises(ValueError) as exception:
      global_env_valid("prod")
    self.assertTrue("Invalid global env" in exception.exception.message)
    with self.assertRaises(ValueError) as exception:
      global_env_valid("not_global")
    self.assertTrue("Invalid global env" in exception.exception.message)
    with self.assertRaises(ValueError) as exception:
      global_env_valid("not_mgmt")
    self.assertTrue("Invalid global env" in exception.exception.message)

if __name__ == '__main__':
   unittest.main()
