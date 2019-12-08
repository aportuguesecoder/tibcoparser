import getopt
import sys
import zipfile
import subprocess
import os
import shutil
import re
import xml.etree.ElementTree as ET
import xml.dom.minidom as MN

'''
Created by Armando Gomes (long long time ago, circa 2014)
https://armandogom.es

if you want to modify this code, feel free to do so.
Oh, and share your modifications. They might help someone.
'''

_Slash = "\\"
_EAR = ""
_EARFileName = ""
_PARFileName = ""
_SARFileName = 'Shared Archive.sar'
_XMLFileName = ""
_VariablesInEAR = [] #Structure: [Variable Name]
_VariablesInXML = [] #Structure: [Variable Type (Boolean, Int, Password, String), Variable Name, Configuration Required, Variable Value]
_VariablesDefault = [] #Structure: [Variable Type (Boolean, Int, Password, String), Variable Name, Configuration Required]
_VariablesFinal = [] #Structure: [Variable Type (Boolean, Int, Password, String), Variable Name, VariableValue]
_VariablesNoConfigurationRequired = [] #Structure: [Variable Type (Boolean, Int, Password, String), Variable Name, Variable Value, Variable Description]
_StagingPath = _Slash + 'staging' + _Slash
_PARStagingPath = _StagingPath + _Slash + 'parstaging' + _Slash
_SARStagingPath = _StagingPath + _Slash + 'sarstaging' + _Slash
_FinalPath = _Slash + 'final' + _Slash
_CurrentPath = os.getcwd()
_FileList = []
_XMLElementList = []

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "he:", ["help", "ear="])
	except getopt.GetoptError as err:
		# print help information and exit:
		print(err) # will print something like "option -a not recognized"
		usage()
		sys.exit(2)
	if len(sys.argv) is 1:
		usage()
		sys.exit(2)
	for o, a in opts:
		if o in ("-h", "--help"):
			usage()
			sys.exit()
			continue
		elif o in ("-e", "--ear"):
			global _EAR 
			_EAR = _CurrentPath + '\\' + a;
			process()
		else:
			print("Argument -e <EAR> is mandatory!")
			usage()
			sys.exit(2)

def usage():
	print("usage: python parser.py -e <EAR>")
	pass

def process():
	global _PARFileName
	print("Validating files...\n")
	validation()
	print("Unzipping EAR...\n")
	unzip(_EAR, _CurrentPath + _StagingPath)
	error = 0
	try:
		print("Unzipping PAR...\n")
		unzip(_CurrentPath + _StagingPath + "\\" + _PARFileName, _CurrentPath + _PARStagingPath)
	except FileNotFoundError:
		print("Error. This is not an Process Archive. Trying Adapter Archive...\n")
		error+=1
	if error > 0:
		try:
			_PARFileName = _EARFileName.split('.')[0] + '.aar'
			print("Unzipping AAR...\n")
			unzip(_CurrentPath + _StagingPath + "\\" + _PARFileName, _CurrentPath + _PARStagingPath)
		except FileNotFoundError:
			print("New error! This is not a valid TIBCO EAR file. Logging out...\n")
	print("Unzipping SAR...\n")
	unzip(_CurrentPath + _StagingPath + "\\" + _SARFileName, _CurrentPath + _SARStagingPath)
	print("Unzipping finished. Listing variables from EAR...\n")
	getVariablesFromEAR()
	print("Listed all variables in EAR. Found " + str(len(_VariablesInEAR)) + " variables. Now listing variables from XML file (TIBCO.XML)...\n")
	getVariablesFromXML()
	print("Listed all variables in XML. Found " + str(len(_VariablesInXML)) + " variables.\n")
	print("Correlating variables between XML and EAR...\n")
	correlateVariables()
	print("Now generating " + _XMLFileName + ".\n")
	generateXML()
	print(_XMLFileName + " generated!. Cleaning up TIBCO.XML...\n")
	cleanTIBCO()
	print("TIBCO.XML is now clean. Zipping everything...\n")
	zip()
	print("Cleaning up staging...\n")
	cleanStaging()
	print("Done! You can find your .EAR and .XML file in final folder.\n")
	copyright()
	openFolder()

def validation():
	if os.path.isdir(_CurrentPath + _StagingPath) is False:
		os.mkdir(_CurrentPath + _StagingPath)
	if os.path.isfile(_EAR) is False:
		print("Invalid filename. Provided: " + _EAR)
		sys.exit()
		pass
	else:
		global _EARFileName
		_EARFileName = _EAR.split("\\")[len(_EAR.split("\\")) - 1]
		global _PARFileName
		_PARFileName = _EARFileName.split('.')[0] + '.par'
		global _XMLFileName
		_XMLFileName = _EARFileName.split('.')[0] + '.xml'
	pass

def unzip(file, path):
	with zipfile.ZipFile(file, 'r') as z:
		z.extractall(path)
		z.close()
	pass

def getVariablesFromEAR():
	getFileList()
	global _FileList
	global _VariablesInEAR
	for filename in _FileList:
		with open(filename, 'r') as fin:
			for line in fin:
				if '%%' in line:
					tempVariables = re.findall(r'%+(.*?)%+', line)
					for tempVar in tempVariables:
						if tempVar not in _VariablesInEAR:
							_VariablesInEAR.append(tempVar.strip(' \t\n\r'))
							pass
						pass
					pass
				else:
					tempVariables = re.findall(r'GlobalVariables\/(.*?)(?=[,)\'"\s])', line)
					for tempVar in tempVariables:
						if tempVar not in _VariablesInEAR:
							_VariablesInEAR.append(tempVar.strip(' \t\n\r'))
							pass
						pass
					pass
				pass
			pass
		pass
	pass

def getFileList():
	global _FileList
	for root, subFolders, files in os.walk(_CurrentPath + _SARStagingPath):
		for file in files:
			fileName, fileExtension = os.path.splitext(os.path.join(root,file))
			if fileExtension not in ('.xsd', '.wsdl'):
				_FileList.append(os.path.join(root,file))
			pass
		pass
	for root, subFolders, files in os.walk(_CurrentPath + _PARStagingPath):
		for file in files:
			fileName, fileExtension = os.path.splitext(os.path.join(root,file))
			if fileExtension not in ('.xsd', '.wsdl'):
				_FileList.append(os.path.join(root,file))
			pass
		pass
	pass
	
def getVariablesFromXML():
	global _VariablesInXML
	global _VariablesNoConfigurationRequired
	text = ""
	required = ""
	value = ""
	description = ""
	doc = ET.parse(_CurrentPath + _StagingPath + '\\TIBCO.xml')
	root = doc.getroot()
	npv = None
	added = 0
	for child in root:
		added = 0
		if 'NameValuePairs' in child.tag:
			for subchild in child:
				if 'name' in subchild.tag and 'Global Variables' in subchild.text:
					_XMLElementList.append([child, 1])
					npv = child
					added = 1
		if added == 0:
			_XMLElementList.append([child, 0])

	'''
	Change this shit!
	'''

	for node in npv:
		for subnode in node:
			if 'name' in subnode.tag:
				text = subnode.text
			elif 'value' in subnode.tag:
				value = subnode.text
			elif 'requiresConfiguration' in subnode.tag:
				required = subnode.text
			elif 'description' in subnode.tag:
				description = subnode.text
			pass
		if 'false' in required:
			_VariablesNoConfigurationRequired.append([node.tag.split('}')[1], text, value, description])
		else:
			_VariablesInXML.append([node.tag.split('}')[1], text, required, value])
			pass
	pass

def correlateVariables():
	global _VariablesFinal
	for variable in _VariablesInXML:
		if variable[1] in _VariablesInEAR:
			_VariablesFinal.append(variable)
			pass
		pass
	pass
	
def generateXML():
	root = ET.Element("NVPairs")
	root.set("name", "Global Variables")
	for variable in sorted(_VariablesFinal):
		if 'NameValuePair' in variable[0]:
			nvp = ET.SubElement(root, variable[0])
			name = ET.SubElement(nvp, "name")
			name.text = variable[1]
			value = ET.SubElement(nvp, "value")
			value.text = variable[3]
			pass
	tree = ET.ElementTree(root)
	f = open(_CurrentPath + _FinalPath + _XMLFileName,'w')
	f.write(prettify(root, False))
	f.close()
	pass

def cleanTIBCO():
	#TIBCO.XML has 11 entries inside <DeploymentDescriptors>
	#NameValuePairs @ 8
	doc = ET.parse(_CurrentPath + _StagingPath + '\\TIBCO.xml')
	root = doc.getroot()
	npv = None
	for child in root:
		if 'NameValuePairs' in child.tag:
			for subchild in child:
				if 'name' in subchild.tag and 'Global Variables' in subchild.text:
					print(subchild.tag)
					npv = child
					break;
	root.remove(npv)
	index = 0
	for element in _XMLElementList:
		index+=1
		if element[1] == 1:
			break	
	# Generate new NPV
	nnpv = ET.Element("ns0:NameValuePairs")
	name = ET.SubElement(nnpv, 'ns0:name')
	name.text = 'Global Variables'
	for variable in sorted(_VariablesFinal):
		if 'NameValuePair' in variable[0]:
			local = ET.SubElement(nnpv, "ns0:" + variable[0])
			name = ET.SubElement(local, "ns0:name")
			name.text = variable[1]
			value = ET.SubElement(local, "ns0:value")
			value.text = variable[3]
			requiresConfiguration = ET.SubElement(local, "ns0:requiresConfiguration")
			requiresConfiguration.text = variable[2]
			pass
	for variable in sorted(_VariablesNoConfigurationRequired):
		if 'NameValuePair' in variable[0]:
			local = ET.SubElement(nnpv, "ns0:" + variable[0])
			name = ET.SubElement(local, "ns0:name")
			name.text = variable[1]
			value = ET.SubElement(local, "ns0:value")
			value.text = variable[2]
			description = ET.SubElement(local, "ns0:description")
			description.text = variable[3]
			requiresConfiguration = ET.SubElement(local, "ns0:requiresConfiguration")
			requiresConfiguration.text = 'false'
	root.insert(index,nnpv)
	f = open(_CurrentPath + _StagingPath + '\\TIBCO.xml','w')
	f.write(prettify(root,False))
	f.close()
	flines = []
	filtered = []
	with open(_CurrentPath + _StagingPath + '\\TIBCO.xml','r') as myfile:
		flines=myfile.readlines()
	myfile.close()
		
	f = open(_CurrentPath + _StagingPath + '\\TIBCO.xml','w',newline='\n')
	for line in flines:
		if '<' in line:
			f.write(line.replace('\r\n', '\n').replace('\r', ''))
	f.close()
	pass

def cleanStaging():
	cleanFolder(_CurrentPath + _StagingPath)
	pass
	
def cleanFolder(folder):
	shutil.rmtree(folder)
	pass
	
def zip():
	cleanFolder(_CurrentPath + _PARStagingPath)
	cleanFolder(_CurrentPath + _SARStagingPath)
	zipf = zipfile.ZipFile(_CurrentPath + _FinalPath + _EARFileName, 'w', zipfile.ZIP_DEFLATED)
	basedir = _CurrentPath + _StagingPath
	for root, dirs, files in os.walk(basedir):
		for fn in files:
			absfn = os.path.join(root, fn)
			zfn = absfn[len(basedir)+len(os.sep) - 1:]
			zipf.write(absfn, zfn)
			pass
		pass
	zipf.close()
	pass

def copyright():
	print("[*] Created by Armando Gomes (hello@armandogom.es) [*]")
	print("[*]    See other work at https://armandogom.es     [*]")
	pass

def openFolder():
	subprocess.Popen(r'explorer ' + _CurrentPath + _FinalPath)
	pass
	
def prettify(elem, newline):
	rough_string = ET.tostring(elem, 'utf-8')
	reparsed = MN.parseString(rough_string)
	if newline is True:
		return reparsed.toprettyxml(indent="\t",newl='')
	else:
		return reparsed.toprettyxml(indent="\t")

if __name__ == "__main__":
	main()
