#-------------------------------------------------------------
# Name:       Property Report
# Purpose:    Will zoom to selected property, showing over the top of imagery. Will also produce
# a small report about the property.
# Author:     Shaun Weston (shaun.weston@splicegroup.co.nz)
# Created:    17/05/2013
# Copyright:   (c) Splice Group
# ArcGIS Version:   10.1
# Python Version:   2.7
#--------------------------------

# Import modules and enable data to be overwritten
import os
import sys
import arcpy
import string
import uuid
import xml.etree.ElementTree as ET
arcpy.env.overwriteOutput = True
    
# Pass l the function
def gotoFunction(configFile,propertyID,propertyField,propertyFeatureClass,layerSymbology,propertyReportMXD,OutputFile): # Get parameters from ArcGIS Desktop tool by seperating by comma e.g. (var1 is 1st parameter,var2 is 2nd parameter,var3 is 3rd parameter)  
    try:
        # Select the property by ID
        arcpy.Select_analysis(propertyFeatureClass, "in_memory\PropertySelected", propertyField + " = '" + str(propertyID) + "'")

        # Setup map document
        mxd = arcpy.mapping.MapDocument(propertyReportMXD)
        # Reference data frame and the layer
        dataFrame = arcpy.mapping.ListDataFrames(mxd, "Layers")[0]

        # Add the selected feature to the map
        arcpy.MakeFeatureLayer_management("in_memory\PropertySelected", "Property Selected")
        selectionLayer = arcpy.mapping.Layer("Property Selected")
        arcpy.mapping.AddLayer(dataFrame,selectionLayer)
        selectionLayer = arcpy.mapping.ListLayers(mxd, "Property Selected", dataFrame)[0]

        # Zoom to feature boundary               
        arcpy.SelectLayerByAttribute_management(selectionLayer, "NEW_SELECTION")
        dataFrame.extent = selectionLayer.getSelectedExtent(False)
        # Take current scale and buffer it out 200%
        trueScale = dataFrame.scale * 2
        # Round scale to a more general number and clear selection
        dataFrame.scale = round(trueScale, -2)
        arcpy.SelectLayerByAttribute_management(selectionLayer, "CLEAR_SELECTION")

        # Update the symbology
        symbologyLayer = arcpy.mapping.Layer(layerSymbology)       
        arcpy.mapping.UpdateLayer(dataFrame, selectionLayer, symbologyLayer, True)

        # Refresh the view
        arcpy.RefreshActiveView()

        # Update the text elements from the config file
        # Convert config file to xml
        configFileXML = ET.parse(configFile)    
        # Import and reference the configuration file
        root = configFileXML.getroot()        

        # Iterate through each of the fields listed in the configuration file
        for child in root.find("fields"):
            # Get the value of the field from the feature class
            cursor = arcpy.SearchCursor("in_memory\PropertySelected")            
            for row in cursor:
                value = row.getValue(child.find("fieldName").text)

            # Get the text element from the map document and update with value from feature class
            for elm in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):
               if elm.name == child.find("placeholder").text:
                  # If value is valid, otherwise make it blank
                  if (value):
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


        # Export page to output folder
        OutputFileName = 'Report_{}.{}'.format(str(uuid.uuid1()), "PDF")
        OutputFile = os.path.join(arcpy.env.scratchFolder, OutputFileName)
        arcpy.mapping.ExportToPDF(mxd, OutputFile, resolution=200)
        arcpy.SetParameterAsText(6, OutputFile)
        
        pass
    except arcpy.ExecuteError:
        arcpy.AddMessage(arcpy.GetMessages(2)) 
        print arcpy.GetMessages(2)
    except Exception as e:
        arcpy.AddMessage(e.args[0])       
        print e.args[0]
# End of function

# This test allows the script to be used from the operating
# system command prompt (stand-alone), in a Python IDE, 
# as a geoprocessing script tool, or as a module imported in
# another script
if __name__ == '__main__':
    # Arguments are optional - If running from ArcGIS Desktop tool, parameters will be loaded into *argv
    argv = tuple(arcpy.GetParameterAsText(i)
        for i in range(arcpy.GetArgumentCount()))
    gotoFunction(*argv)