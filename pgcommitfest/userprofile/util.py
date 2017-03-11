from Crypto.Hash import SHA256
from Crypto import Random
from email.utils import formataddr
from email.header import Header

from models import UserProfile

def generate_random_token():
	"""
	Generate a random token of 64 characters. This token will be
	generated using a strong random number, and then hex encoded to make
	sure all characters are safe to put in emails and URLs.
	"""
	s = SHA256.new()
	r = Random.new()
	s.update(r.read(250))
	return s.hexdigest()


class UserWrapper(object):
	def __init__(self, user):
		self.user = user

	@property
	def email(self):
		try:
			up = UserProfile.objects.get(user=self.user)
			if up.selectedemail and up.selectedemail.confirmed:
				return up.selectedemail.email
			else:
				return self.user.email
		except UserProfile.DoesNotExist:
			return self.user.email

	@property
	def encoded_email_header(self):
		return formataddr((
			str(Header(u"%s %s" % (self.user.first_name, self.user.last_name), 'utf-8')),
			self.email))
