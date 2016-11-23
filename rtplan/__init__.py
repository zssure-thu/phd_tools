class rtplan:
	def __init__(self,filename, **kwargs):
		#defaults
		self.nprims=4e10
		self.norm2nprim=True
		self.MSW_to_protons=True
		self.killzero=True
		self.fixMSWsums=True
		
		for key in ('fixMSWsums', 'nprims', 'MSW_to_protons', 'killzero', 'norm2nprim'):
			if key in kwargs:
				setattr(self, key, kwargs[key])
		
		self.TotalMetersetWeight = 0.
		self.layers = []
		self.spots = []
		self.fields = []
		self.layerhistrange = []
		self.rangetable = []
		self.fieldids = [] #not sure why we have this
		
		sourcefile = open(filename,'r')
	
		capture_NbOfScannedSpots = 0
		capture_Spots = 0
		capture_CumulativeMetersetWeight = 0
		capture_TotalMetersetWeight = 0
		capture_Energy = 0
		capture_Energy_first = 1
		capture_FieldID = 0
		capture_ControlPointIndex = 0
		capture_GantryAngle = 0

		previous_CumulativeMetersetWeight = 0
		CumulativeMetersetWeight = 0
		MSWfactor = 0
		Energy = 0
		Energy_first = 0
		Energy_last = 0
		NbOfScannedSpots = 0
		FieldID = 0
		ControlPointIndex = 0
		GantryAngle = 0

		for index, line in enumerate(sourcefile):
			newline = line.strip()
			if len(newline)==0:
				continue
		
			if newline[0] == "#":
				#we are reading a fieldname
				#stop reading spots if we were doing that.
				capture_Spots = 0
				newline = newline.replace('#','')
				if newline == 'CumulativeMetersetWeight':
					#if the field is CumulativeMetersetWeight,
					#we're engaging capture mode because next we'll get
					#energy and number of spots, and thus we can 
					#calculate fluence.
					capture_CumulativeMetersetWeight = 1
					continue
	
				if newline == 'Energy (MeV)':
					capture_Energy = 1
					continue
	
				if newline == 'TotalMetersetWeightOfAllFields':
					capture_TotalMetersetWeight = 1
					continue
	
				if newline == 'NbOfScannedSpots':
					capture_NbOfScannedSpots = 1
					continue
			
				if newline == 'GantryAngle':
					#new field ==  new dataset
					capture_GantryAngle = 1
					continue
			
				if newline == 'FieldID':
					#new field ==  new dataset
					# fieldID doesnt have to be incremental!
					capture_FieldID = 1
					continue
			
				if newline == 'ControlPointIndex':
					capture_ControlPointIndex = 1
					continue
				
				if newline == 'X Y Weight':
					capture_Spots = 1
					continue

			if capture_ControlPointIndex == 1:
				#CPI in rtplan starts at 0
				ControlPointIndex = int(newline)
				capture_ControlPointIndex = 0
		
			if capture_GantryAngle == 1:
				GantryAngle = int(newline)
				capture_GantryAngle = 0
		
			if capture_CumulativeMetersetWeight == 1:
				#Note: CumulativeMetersetWeight is the amount of dose/fluence delivered so far.
				#It does NOT!!!! include the dose/fluence in this particular controlpoint.
				#Note2: CPIs are grouped in pairs: the first defines the weights per spot, the second the total CMW.
				new_CumulativeMetersetWeight = float(newline)
				if new_CumulativeMetersetWeight == 0:
					#If it's 0, we are at the start of a new Field.
					CumulativeMetersetWeight = 0
					previous_CumulativeMetersetWeight = 0
					capture_CumulativeMetersetWeight = 0
					continue
				else:
					#Can this happen?
					previous_CumulativeMetersetWeight = CumulativeMetersetWeight
					CumulativeMetersetWeight = new_CumulativeMetersetWeight
					capture_CumulativeMetersetWeight = 0

			if capture_FieldID == 1:
				FieldID = int(newline)
				self.fieldids.append(FieldID)
				capture_FieldID = 0
		
			if capture_Energy == 1:
				capture_Energy = 0
				new_Energy = float(newline)
				if new_Energy == 0:
					#end of the Field, we still have to record the CMW though!!!!
					capture_Energy_first = 1
					Energy_last = Energy
					Energy = new_Energy
					continue
				Energy = new_Energy
				if capture_Energy_first == 1:
					Energy_first = new_Energy
					capture_Energy_first = 0

			if capture_TotalMetersetWeight == 1:
				#it appears the sums never are really quite correct, so we'll set later if and when converted to nb_prots
				self.TotalMetersetWeight = float(newline)
				capture_TotalMetersetWeight = 0
		
			if capture_NbOfScannedSpots == 1:
				capture_NbOfScannedSpots = 0
				if CumulativeMetersetWeight == previous_CumulativeMetersetWeight:
					#First CPI of the energylayer, so just set the value and be done.
					NbOfScannedSpots = int(newline)
					continue
				if Energy == 0:
					#End of the field, here NbOfScannedSpots = int(newline) = 0, so dont overwrite.
					self.layers.append([FieldID,Energy_last,(CumulativeMetersetWeight-previous_CumulativeMetersetWeight),NbOfScannedSpots])
					self.fields.append([FieldID,(ControlPointIndex)/2+1,Energy_first,Energy_last,CumulativeMetersetWeight,GantryAngle])
				else:
					NbOfScannedSpots = int(newline)
					self.layers.append([FieldID,Energy,(CumulativeMetersetWeight-previous_CumulativeMetersetWeight),NbOfScannedSpots])
					
			if capture_Spots == 1:
				#Only capture spots for first of pairs of CMWs
				if CumulativeMetersetWeight == previous_CumulativeMetersetWeight:
					x,y,weight = newline.split(' ')
					if self.killzero and float(weight) == 0:
						continue
					self.spots.append([FieldID,Energy,float(x),float(y),float(weight)])
				#Because Spots are multiline, we stop it when handling lines starting with '#', see top of function.
		
	
		sourcefile.close()
		self.autolayerhistrange()
		self.autospothistrange()
		if self.fixMSWsums == True:
			self.fix_MSW_sums()
		if self.MSW_to_protons == True:
			self.msw_to_prot()
		if self.norm2nprim == True:
			self.norm_to_nprim()


	def autolayerhistrange(self):
		#find high and low points for histograms
		#TODO can I do without this? can the edges for a TH1D be changed afterwards?
		low = 1000000 #1TeV seems like a fine upperlimit
		high = 0
		for entry in self.fields:
			low = min(low,entry[2],entry[3])
			high = max(high,entry[2],entry[3])
	
		#Make sure the upper and lower bins are within view.
		low-=1
		high+=1
		self.layerhistrange=[low,high]


	def autospothistrange(self):
		#find high and low points for histograms
		#TODO can I do without this? can the edges for a TH1D be changed afterwards?
		low = 0 #0 is the lowest, obviously
		high = 0
		for entry in self.spots:
			high = max(high,entry[-1])
	
		#Make sure the upper and lower bins are within view doesnt seem necesary.
		#low-=1
		#high+=1
		self.spothistrange=[low,high]


	def getlayerdata(self, layerhistrange=None):
		if layerhistrange is not None:
			self.layerhistrange = layerhistrange

		#array of data
		histos=[]
		
		# Create some histograms
		for field in self.fields:
			curfieldid = field[0]
		#for i in range(len(self.fieldids)):
			#curfieldid = self.fieldids[i]
			xv=[]
			yv=[]
			for cp in self.layers:
				if cp[0] == curfieldid:
					xv.append(cp[1]) #energy
					yv.append(cp[2]) #nbprots
			histos.append([xv,yv])
		
		return histos


	def getspotdata(self, spothistrange=None):
		if spothistrange is not None:
			self.spothistrange = spothistrange

		#array of data, not really a histo
		histos=[]
		
		# Create some histograms

		for field in self.fields:
			curfieldid = field[0]
		#for i in range(len(self.fieldids)):
			#curfieldid = self.fieldids[i]
			xv=[]
			yv=[]
			for spot in self.spots:
				if spot[0] == curfieldid:
					xv.append(spot[1]) #energy
					yv.append(spot[-1]) #nbprots
			histos.append([xv,yv])
		
		return histos


	def ConvertMuToProtons(self,weight,energy):
		#straight from GateSourceTPSPencilBeam, seems to introduce small energy-dep on #prots/MU
		K=37.60933
		SP=9.6139E-09 * energy**4 - 7.0508E-06 * energy**3 + 2.0028E-03 * energy**2 - 2.7615E-01 * energy**1 + 2.0082E+01 * energy**0
		PTP=1.
		Gain=3./(K*SP*PTP*1.602176E-10)
		return weight*Gain
	

	def fix_MSW_sums(self):
		#fixes layer MSWs and total MSW. Based on experience, neither can be trusted. IN SPOT WE TRUST
		
		#Do not assume fieldid is 0 or 1 indexed (can be higher).
		
		spotsum = [0.]*len(self.spots)
		laysum = [0.]*len(self.layers)
		fieldsum = [0.]*len(self.fields)
		
		print len(self.layers),len(self.fields)
		
		for i,field in enumerate(self.fields):
			fieldsum[i] = field[4]
		
		for i,layer in enumerate(self.layers):
			laysum[i] = layer[2]
		
		for i,spot in enumerate(self.spots):
			spotsum[i] += spot[4]
		
		print "MSW sums in plan file:"
		print self.TotalMetersetWeight,sum(fieldsum),sum(laysum),sum(spotsum)
		
		#we can assume self.layers is in same order as field. so no need to account for fieldid.
		
		fieldind=0 #first field index is zero.
		lastfield=self.spots[0][0]#take FIELDID of first spot.
		layind=0 #first layer index is zero.
		lastenergy=self.spots[0][1]#take ENERGY of first spot.
		
		self.TotalMetersetWeight = 0. #reset
		laysum = [0.]*len(self.layers)
		fieldsum = [0.]*len(self.fields)
		
		for spot in self.spots:
			if spot[0] != lastfield:
				#we changed FIELD. update layer info
				lastfield = spot[0]
				fieldind += 1
				#if we changed field, we ALSO change layer! Must check before we check spotenergy
				lastenergy = spot[1]
				layind += 1
			if spot[1] != lastenergy:
				#we changed LAYER. update layer info
				lastenergy = spot[1]
				layind += 1
				
			self.TotalMetersetWeight += spot[4]
			laysum[layind] += spot[4]
			fieldsum[fieldind] += spot[4]
		
		#terugzetten
		for field,fsum in zip(self.fields,fieldsum):
			field[4] = fsum
		for layer,lsum in zip(self.layers,laysum):
			layer[2] = lsum
		
		print "MSW sums in plan file after fix:"
		print self.TotalMetersetWeight,sum(fieldsum),sum(laysum),sum(spotsum)


	def msw_to_prot(self):
		#since its not linear, we must update layer and field sums.
		
		spotsum = [0.]*len(self.spots)
		laysum = [0.]*len(self.layers)
		fieldsum = [0.]*len(self.fields)
		
		for i,field in enumerate(self.fields):
			fieldsum[i] = field[4]
		
		for i,layer in enumerate(self.layers):
			laysum[i] = layer[2]
		
		for i,spot in enumerate(self.spots):
			spotsum[i] += spot[4]
		
		print "MSW sums:"
		print self.TotalMetersetWeight,sum(fieldsum),sum(laysum),sum(spotsum)
				
		fieldind=0 #first field index is zero.
		lastfield=self.spots[0][0]#take FIELDID of first spot.
		layind=0 #first layer index is zero.
		lastenergy=self.spots[0][1]#take ENERGY of first spot.
		
		self.TotalMetersetWeight = 0. #reset
		laysum = [0.]*len(self.layers)
		fieldsum = [0.]*len(self.fields)
		
		for spot in self.spots:
			if spot[0] != lastfield:
				#we changed FIELD. update layer info
				lastfield = spot[0]
				fieldind += 1
				#if we changed field, we ALSO change layer! Must check before we check spotenergy
				lastenergy = spot[1]
				layind += 1
			if spot[1] != lastenergy:
				#we changed LAYER. update layer info
				lastenergy = spot[1]
				layind += 1
			
			E = spot[1]
			MSW = spot[4]
			spot[4] = self.ConvertMuToProtons(MSW, E)
			spotsum[i] += spot[4] #just for the final report
			self.TotalMetersetWeight += spot[4]
			laysum[layind] += spot[4]
			fieldsum[fieldind] += spot[4]
		
		#terugzetten
		for field,fsum in zip(self.fields,fieldsum):
			field[4] = fsum
		for layer,lsum in zip(self.layers,laysum):
			layer[2] = lsum
		
		print "Proton count sums:"
		print self.TotalMetersetWeight,sum(fieldsum),sum(laysum),sum(spotsum)
		
		print "Conversion to correct numbers of protons complete."


	def norm_to_nprim(self):
		try:
			assert self.nprims != self.TotalMetersetWeight
		except AssertionError:
			print "No normalization needed, skipping..."
		MSWfactor = self.nprims/self.TotalMetersetWeight
		for layer in self.layers:
			layer[2] *= MSWfactor
		for spot in self.spots:
			spot[4] *= MSWfactor
		for field in self.fields:
			field[4] *= MSWfactor
		self.TotalMetersetWeight *= MSWfactor
		
		print "Normalization to",self.nprims,"numbers of protons complete."
