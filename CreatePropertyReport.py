#-------------------------------------------------------------
# Name:       ArcGIS Property Report
# Purpose:    Highlights and zooms to a selected property and produces
# a report about the property showing it over the top of a basemap.         
# Author:     Shaun Weston (shaun_weston@eagle.co.nz)
# Date Created:    09/08/2013
# Last Updated:    19/03/2014
# Copyright:   (c) Eagle Technology
# ArcGIS Version:   10.1/10.2
# Python Version:   2.7
#--------------------------------

# Import modules and enable data to be overwritten
import os
import sys
import arcpy
import logging
import smtplib
import string
import json
import urllib
import uuid
import xml.etree.ElementTree as ET

# Enable data to be overwritten
arcpy.env.overwriteOutput = True

# Set global variables
enableLogging = "false" # Use logger.info("Example..."), logger.warning("Example..."), logger.error("Example...")
logFile = "" # os.path.join(os.path.dirname(__file__), "Example.log")
sendErrorEmail = "false"
emailTo = ""
emailUser = ""
emailPassword = ""
emailSubject = ""
emailMessage = ""
output = None
    
# Start of main function
def mainFunction(propertyID,propertyMapService,propertyIDField,propertyAddressField,configFile,propertySymbology,propertyReportMXD,scaleBuffer,scale,OutputFile): # Get parameters from ArcGIS Desktop tool by seperating by comma e.g. (var1 is 1st parameter,var2 is 2nd parameter,var3 is 3rd parameter)              
    try:
        # Logging
        if (enableLogging == "true"):
            # Setup logging
            logger, logMessage = setLogging(logFile)
            # Log start of process
            logger.info("Process started.")
            
        # --------------------------------------- Start of code --------------------------------------- #
        
        # ------------- Select the property by ID ------------------------
        arcpy.AddMessage("Selecting property...")
        # Create property features
        # Create map service query         
        mapServiceQuery = propertyMapService + "/query?where=" + propertyIDField + "=" + "'" + str(propertyID) + "'" + "&text=&objectIds=&time=&geometry=&geometryType=esriGeometryPolygon&inSR=&spatialRel=esriSpatialRelIntersects&relationParam=&outFields=*&returnGeometry=true&maxAllowableOffset=&geometryPrecision=&outSR=&returnIdsOnly=false&returnCountOnly=false&orderByFields=&groupByFieldsForStatistics=&outStatistics=&returnZ=false&returnM=false&gdbVersion=&f=pjson"
        urlResponse = urllib.urlopen(mapServiceQuery);   
        # Get json for feature returned
        mapServiceQueryJSONData = json.loads(urlResponse.read())          
        # Get the geometry and create temporary feature class       
        propertyGeometryJSON = mapServiceQueryJSONData["features"][0]["geometry"]          
        # Add spatial reference to geometry
        propertySpatialReference = mapServiceQueryJSONData["spatialReference"]["wkid"]
        propertyGeometryJSON["spatialReference"] = {'wkid' : propertySpatialReference}     
        # Convert to feature classes         
        propertyGeometryPolygon = arcpy.AsShape(propertyGeometryJSON, "True")        
        arcpy.CopyFeatures_management(propertyGeometryPolygon, "in_memory\PropertySelectedPolygon")
        # Get the attributes
        propertyAddress = str(mapServiceQueryJSONData["features"][0]["attributes"].get(propertyAddressField))        
        # ----------------------------------------------------------------      
        
        # ------------- Setup map document ------------------------
        mxd = arcpy.mapping.MapDocument(propertyReportMXD)
        # Reference data frame and the layer
        dataFrame = arcpy.mapping.ListDataFrames(mxd, "Layers")[0]
        # ----------------------------------------------------------------

        # ------------- Add the selected feature to the map ------------------------
        arcpy.AddMessage("Adding property to map and zooming to it...")
        arcpy.MakeFeatureLayer_management("in_memory\PropertySelectedPolygon", "Property Selected")           
        selectionLayer = arcpy.mapping.Layer("Property Selected")
        arcpy.mapping.AddLayer(dataFrame,selectionLayer)
        selectionLayer = arcpy.mapping.ListLayers(mxd, "Property Selected", dataFrame)[0]
        # ----------------------------------------------------------------

        # ------------- Zoom to feature boundary ------------------------                
        arcpy.SelectLayerByAttribute_management(selectionLayer, "NEW_SELECTION")
        dataFrame.extent = selectionLayer.getSelectedExtent(False)
        
        # Take current scale and buffer it out by the percentage for urban defined
        trueScale = dataFrame.scale * float((float(scaleBuffer)/100)+1)
        # If scale provided, set it to that, otherwise round scale to a more general number and clear selection
        if scale:
            dataFrame.scale = scale
        else:
            dataFrame.scale = round(trueScale, -2)    
        arcpy.SelectLayerByAttribute_management(selectionLayer, "CLEAR_SELECTION")
        
        # Update the symbology
        symbologyLayer = arcpy.mapping.Layer(propertySymbology)       
        arcpy.mapping.UpdateLayer(dataFrame, selectionLayer, symbologyLayer, True)
        # ----------------------------------------------------------------

        # ------------- Replace the title, notes and address text with the paramater values ------------------------ 
        arcpy.AddMessage("Adding address ...")
        for elm in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):
               if elm.name == "Address":
                   # Set the address
                   elm.text = propertyAddress
        # ----------------------------------------------------------------
        
        # ------------- Update the text elements from the config file ------------------------
        arcpy.AddMessage("Updating report text...")
        # Convert config file to xml
        configFileXML = ET.parse(configFile)    
        # Import and reference the configuration file
        root = configFileXML.getroot()        

        # Iterate through each of the fields listed in the configuration file for the property report
        for child in root.find("fields"):     
            # Get the value of the field from the map service
            value = str(mapServiceQueryJSONData["features"][0]["attributes"].get(child.find("fieldName").text))
            # Get the text element from the map document and update with value from feature class
            for elm in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):               
               if elm.name == child.find("placeholder").text:                 
                  # If value is valid, otherwise make it blank
                  if (value != "None"):
                      # If value text length is too long then add new lines
                      if (len(str(value)) > 50):
                          # Split string by spaces
                          stringArray = value.split()

                          # For each of the words, build the text
                          newText = ""
                          textCounter = ""
                          for i in range(len(stringArray)):
                              # Add to element text until reaches max line width then add new line
                              if (textCounter == ""):
                                  newText = newText + stringArray[i]
                              else:
                                  newText = newText + " " + stringArray[i]
                              textCounter = textCounter + " " + stringArray[i]
                              if (len(textCounter) > 50):
                                  # Add new line
                                  textCounter = ""
                                  newText = newText + "\r\n"
                          # Set the text element
                          elm.text = newText                              
                      # Otherwise just replace text in text element
                      else:
                          if (child.find("format").text == "Currency"):                           
                              elm.text = "$ " + '{:12,.2f}'.format(float(value))
                          elif (child.find("format").text == "Float"):      
                              elm.text = '{:20,.2f}'.format(float(value))                              
                          else:
                              elm.text = value
                  else:
                      elm.text = " "
        # ----------------------------------------------------------------

        # ------------- Export page to output folder ------------------------
        arcpy.AddMessage("Creating report...")
        # Refresh the view
        arcpy.RefreshActiveView()
        OutputFileName = 'Report_{}.{}'.format(str(uuid.uuid1()), "PDF")
        OutputFile = os.path.join(arcpy.env.scratchFolder, OutputFileName)
        arcpy.mapping.ExportToPDF(mxd, OutputFile, jpeg_compression_quality=90, resolution=200)
        arcpy.SetParameterAsText(9, OutputFile)
        # ----------------------------------------------------------------
        
        # --------------------------------------- End of code --------------------------------------- #  
            
        # If called from gp tool return the arcpy parameter   
        if __name__ == '__main__':
            # Return the output if there is any
            if output:
                arcpy.SetParameterAsText(1, output)
        # Otherwise return the result          
        else:
            # Return the output if there is any
            if output:
                return output      
        # Logging
        if (enableLogging == "true"):
            # Log end of process
            logger.info("Process ended.")
            # Remove file handler and close log file            
            logging.FileHandler.close(logMessage)
            logger.removeHandler(logMessage)
        pass
    # If arcpy error
    except arcpy.ExecuteError:           
        # Build and show the error message
        errorMessage = arcpy.GetMessages(2)   
        arcpy.AddError(errorMessage)           
        # Logging
        if (enableLogging == "true"):
            # Log error          
            logger.error(errorMessage)                 
            # Remove file handler and close log file
            logging.FileHandler.close(logMessage)
            logger.removeHandler(logMessage)
        if (sendErrorEmail == "true"):
            # Send email
            sendEmail(errorMessage)
    # If python error
    except Exception as e:
        errorMessage = ""
        # Build and show the error message
        for i in range(len(e.args)):
            if (i == 0):
                errorMessage = str(e.args[i])
            else:
                errorMessage = errorMessage + " " + str(e.args[i])
        arcpy.AddError(errorMessage)              
        # Logging
        if (enableLogging == "true"):
            # Log error            
            logger.error(errorMessage)               
            # Remove file handler and close log file
            logging.FileHandler.close(logMessage)
            logger.removeHandler(logMessage)
        if (sendErrorEmail == "true"):
            # Send email
            sendEmail(errorMessage)            
# End of main function

# Start of set logging function
def setLogging(logFile):
    # Create a logger
    logger = logging.getLogger(os.path.basename(__file__))
    logger.setLevel(logging.DEBUG)
    # Setup log message handler
    logMessage = logging.FileHandler(logFile)
    # Setup the log formatting
    logFormat = logging.Formatter("%(asctime)s: %(levelname)s - %(message)s", "%d/%m/%Y - %H:%M:%S")
    # Add formatter to log message handler
    logMessage.setFormatter(logFormat)
    # Add log message handler to logger
    logger.addHandler(logMessage) 

    return logger, logMessage               
# End of set logging function


# Start of send email function
def sendEmail(message):
    # Send an email
    arcpy.AddMessage("Sending email...")
    # Server and port information
    smtpServer = smtplib.SMTP("smtp.gmail.com",587) 
    smtpServer.ehlo()
    smtpServer.starttls() 
    smtpServer.ehlo
    # Login with sender email address and password
    smtpServer.login(emailUser, emailPassword)
    # Email content
    header = 'To:' + emailTo + '\n' + 'From: ' + emailUser + '\n' + 'Subject:' + emailSubject + '\n'
    body = header + '\n' + emailMessage + '\n' + '\n' + message
    # Send the email and close the connection
    smtpServer.sendmail(emailUser, emailTo, body)    
# End of send email function


# This test allows the script to be used from the operating
# system command prompt (stand-alone), in a Python IDE, 
# as a geoprocessing script tool, or as a module imported in
# another script
if __name__ == '__main__':
    # Arguments are optional - If running from ArcGIS Desktop tool, parameters will be loaded into *argv
    argv = tuple(arcpy.GetParameterAsText(i)
        for i in range(arcpy.GetArgumentCount()))
    mainFunction(*argv)