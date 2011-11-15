class Sample():
	def __init__(self, data):
		self.data = data
	def probe(self, probe):
		s = ord(self.data[probe / 8]) & (1 << (probe % 8))
		return True if s else False

def sampleiter(data, unitsize):
	for i in range(0, len(data), unitsize):
		yield(Sample(data[i:i+unitsize]))

class Decoder():
	# Probe names with a set of defaults
	probes = {'sdata':0, 'sck':1}

	def __init__(self, unitsize, **kwargs):
		# Metadata comes in here, we don't care for now
		#print kwargs
		self.unitsize = unitsize

		self.probes = Decoder.probes
		self.oldsck = True
		self.rxcount = 0
		self.rxdata = 0
		self.bytesreceived = 0

	def summary(self):
		return "SPI: %d bytes received" % self.bytesreceived

	def decode(self, data):
		# We should accept a list of samples and iterate...
		for sample in sampleiter(data["data"], self.unitsize):

			sck = sample.probe(self.probes["sck"])
			# Sample SDATA on rising SCK
			if sck == self.oldsck:
				continue
			self.oldsck = sck
			if not sck: 
				continue	

			# If this is first bit, save timestamp
			if self.rxcount == 0:
				self.time = data["time"]
			# Receive bit into our shift register
			sdata = sample.probe(self.probes["sdata"])
			if sdata:
				self.rxdata |= 1 << (7 - self.rxcount)
			self.rxcount += 1
			# Continue to receive if not a byte yet
			if self.rxcount != 8:
				continue
			# Received a byte, pass up to sigrok
			outdata = {"time":self.time,
				"duration":data["time"] + data["duration"] - self.time,
				"data":self.rxdata,
				"display":("%02X" % self.rxdata),
				"type":"spi",
			}
			print outdata
			sigrok.put(outdata)
			# Reset decoder state
			self.rxdata = 0
			self.rxcount = 0
			# Keep stats for summary
			self.bytesreceived += 1
			

register = {
	'id': 'spi',
	'name': 'SPI Decoder',
	'longname': '...',
	'desc': 'Decodes SPI frames',
	'longdesc': '...',
	'author': 'Gareth McMullin',
	'email': 'gareth@blacksphere.co.nz',
	'license': 'gplv2+',
	'in': ['logic'],
	'out': ['spi'],
	'probes': [
		# All probes.
	],
	'options': {
		# No options so far.
	},
	# 'start': start,
	# 'report': report,
}

if __name__ == "__main__":
	data = open("spi_dump.bin").read()

	# dummy class to keep Decoder happy for test
	class Sigrok():
		def put(self, data):
			print "\t", data
	sigrok = Sigrok()

	dec = Decoder(driver='ols', unitsize=1, starttime=0)
	dec.decode({"time":0, "duration":len(data), "data":data, "type":"logic"})

	print dec.summary()
else:
	import sigrok

#Tested with:
#  sigrok-cli -d 0:samplerate=1000000:rle=on --time=1s -p 1,2 -a spidec


