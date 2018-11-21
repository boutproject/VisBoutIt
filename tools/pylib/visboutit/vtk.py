#!/usr/bin/python

"""
vtk.py
This python file contains functions required to convert to cylindercal, torodial and ELM systems.
"""

#Import libraries
import visual
import os
import circle
import numpy as np
from scipy import interpolate


def elm(name , time ,zShf_int_p = 0.25, path = None, skip = 1):
    """
       
    elm function: convert the spacial variables to EML coordinate system for a range of time
    
    Inputs
        name: variable name imported from BOUT.dmp files
        time: The end time slice that will be converted, if -1 entire dataset is imported
        zShift Interpolation Percentage: This is used to set the tolerance values for the linear interpolation.
        path: File path to data, if blank then the current working directory is used to look for data
    
    Output
        Timestamped vtk files of the specified variable.
        A text file with the maximum and minimum files.
                
    """
    zShf_int_p = visual.zShf_p_check(zShf_int_p)

    #Get the working dir
    if path == None:
        work_dir = os.getcwd()
    if path != None:
        work_dir = os.chdir(path)
        work_dir = os.getcwd()
    
    grid_file = visual.get("BOUT.inp","grid") # Import grid file name 

    # Get the dimensions and initial value of the variable data.    
    max_t, var_0, nx, ny, nz = visual.dim_all(name)
  
    #ELM
    #Import r,z and zshift from grid file
    r = visual.nc_var(grid_file,'Rxy') # ELM Coordinates
    z = visual.nc_var(grid_file,'Zxy') # ELM Coordinates
    zshift = visual.nc_var(grid_file,'zShift') #ELM Coordinates
    
    max_z,min_z = visual.z_shift_mm(nx,ny,zshift) #Find the max and minimum zshift values
    z_tol = min_z + ((max_z - min_z)* zShf_int_p) # Set tolerance value
    
    #Interpolate the Rxy and Zxy values
    r2,ny2 = visual.zshift_interp2d(nx,ny,zshift,z_tol,r)
    z2,ny2 = visual.zshift_interp2d(nx,ny,zshift,z_tol,z)
    zshift2,ny2 = visual.zshift_interp2d(nx,ny,zshift,z_tol,zshift)
    
    #Create points for ELM 
    pts2 = visual.elm(r2,z2,zshift2,nx,ny2,nz)
    
    ## Set time
    t = time
    # Set t to max_t, if user desires entire dataset
    if t == -1:
        t = max_t
    #If t is greater than number of slices then set to max_t
    if t >= max_t:
        t = max_t
    
    ### Make dir for storing vtk files and image files
    #Check if dir for storing vtk files exsists if not make that dir
    if not os.path.exists("batch"):
        os.makedirs("batch")
    
    #Make dir for storing images
    if not os.path.exists("images"):
        os.makedirs("images")
    
    #Initial max and min values
    var_x, var_y, var_z = var_0[:,0,0], var_0[0,:,0], var_0[0,0,:]
    max_x, max_y, max_z = np.amax(var_x), np.amax(var_y), np.amax(var_z)
    min_x, min_y, min_z = np.amin(var_x), np.amin(var_y),np.amin(var_z)
    max = np.amax((max_x, max_y, max_z))
    min = np.amin((min_x, min_y, min_z))
    
    #If the variable is pressure, import and add the P0 variable to this
    if name == 'P':
        p0 = visual.collect("P0") #Import P0
        add_p = True
    
     #For the entire t range import the spacial values, find min max values, interpolate y, coordinate transform, write to vtk
    q = 0
    while q <= t-1:
        var = visual.var3d(name,q) # collect variable
    
        #Find the min and max values
        var_x, var_y, var_z = var[:,0,0], var[0,:,0], var[0,0,:]
        max_x, max_y, max_z = np.amax(var_x), np.amax(var_y), np.amax(var_z)
        min_x, min_y, min_z = np.amin(var_x), np.amin(var_y), np.amin(var_z)
        max_i = np.amax(np.array((max_x,max_y,max_z)))
        min_i = np.amin(np.array((min_x,min_y,min_z)))
        if max_i >= max:
            max = max_i
        if min_i <= min:
            min = min_i
    
        #Adding p0
        if add_p == True:#Adding P0
            for i in range (nx): # X value
                for j in range(ny): # Y Value
                    var[i,j,:] = var[i,j,:] + p0[i,j]
    
        var2,ny3 = visual.zshift_interp3d(nx,ny,nz,zshift,z_tol,var) # Interpolate Variable
    
        #Convert coordinate section
        vrbl = visual.vtk_var(var2,nx,ny2,nz) #vtk variable
        vtk_path = visual.write_vtk(name,pts2,vrbl,q) # write vtk file
        print "At t = %d, %d Steps remaining" % (q,((t- q)/skip)) # Progress indicator
        q += skip
        
    #Write the Max and min values to file
    mm_array = np.array((max,min))
    np.savetxt('max_min_' + name + '.txt',mm_array) 
    return

def torus(name, time, step = 0.5, skip = 1,path = None, R = None, r = None , dr = None , Bt = None, q = None , isttok = False):
    """
       
    Torus function: Convert to Torodial Coordinate system
    
    Inputs
        name: variable name to import (str)
        time: end time slice to convert to (int), if -1 entire dataset is imported
        step: The gap between the y slices for the y interpolation (float < 1) if 0 then raw data displayed.
        path: File path to data, if blank then the current working directory is used to look for data
        
        Torus settings, if left blank defaults are used all are floats.
        R: Major radius
        r: Minor radius
        dr: Radial width of domain
        Bt: Toroidal magnetic field
        q: Safety factor
        
        isttok: Use the ISTTOK specifications, (Boolean)
        
    Outputs
        Timestamped vtk files of the specified variable.
        A text file with the maximum and minimum files.   
        
    """
    
    #Get the working dir
    if path == None:
        work_dir = os.getcwd()
    if path != None:
        work_dir = os.chdir(path)
        work_dir = os.getcwd()
    
    # Find the max_t, initial value and shape of variable
    max_t, var_0, nx, ny, nz = visual.dim_all(name)
    ny_work = ny
    #Interpolate setup
    #Get number of new points
    if step != 0:
        ny_work = len(np.arange(0,(ny-1),step))
    #Define empty array with increased number of y values
    var_new = np.empty((nx,ny_work,nz),dtype=float)
    
    if isttok == True: # Use ISTTOK specifications?
        R,r,dr,Bt,q = 0.46, 0.085, 0.02, 0.5, 5
    # Import coordinates from function in circle library
    r,z = circle.coordinates(nx,ny_work,nz,R,r,dr,Bt,q) # toroidal coordinates
    pts = visual.torus(r, z, nx, ny_work, nz)  # vtk grid points
    
    # Set time
    t = time
    # Set t to max_t, if user desires entire dataset
    if t == -1:
        t = max_t
    #If t is greater than number of slices then set to max_t
    if t >= max_t:
        t = max_t
    
    # Make dir for storing vtk files and image files
    #Check if dir for storing vtk files exsists if not make that dir
    if not os.path.exists("batch"):
        os.makedirs("batch")
    #Make dir for storing images
    if not os.path.exists("images"):
        os.makedirs("images")
    
    #Initial max and min values
    var_x, var_y, var_z = var_0[:,0,0], var_0[0,:,0], var_0[0,0,:]
    max_x, max_y, max_z = np.amax(var_x), np.amax(var_y), np.amax(var_z)
    min_x, min_y, min_z = np.amin(var_x), np.amin(var_y),np.amin(var_z)
    max = np.amax((max_x, max_y, max_z))
    min = np.amin((min_x, min_y, min_z))
    
    q = 0 
    #For the entire t range import the spacial values, find min max values, interpolate y, coordinate transform, write to vtk
    while q <= t-1:
        var = visual.var3d(name,q) # collect variable
        
        #Find the min and max values
        var_x, var_y, var_z = var[:,0,0], var[0,:,0], var[0,0,:]
        max_x, max_y, max_z = np.amax(var_x), np.amax(var_y), np.amax(var_z)
        min_x, min_y, min_z = np.amin(var_x), np.amin(var_y), np.amin(var_z)
        max_i = np.amax(np.array((max_x,max_y,max_z)))
        min_i = np.amin(np.array((min_x,min_y,min_z)))
        if max_i >= max:
            max = max_i
        if min_i <= min:
            min = min_i
        
        if ny != ny_work: #Interpolate section for all y values
            for i in range(nx):
                for k in range(nz):
                    var_y = var[i,:,k]
                    y = np.arange(0,ny) # Arrange y values in array
                    f = interpolate.interp1d(y,var_y) # Interpolate the data
                    y_new = np.arange(0,(ny-1),step) # Arrange new y values 
                    var_y_new = f(y_new) # interpolate y values
                    var_new[i,:,k] = var_y_new # Store values in new variable
        else:
            var_new = var
        #Convert coordinate section        
        vrbl = visual.vtk_var(var_new,nx,ny_work,nz) # vtk variable
        vtk_path = visual.write_vtk(name,pts,vrbl,q) # write vtk file
        print "At t = %d, %d Steps remaining" % (q,((t- q)/skip)) # Progress indicator
        q += skip
    
    #Write the Max and min values to file
    mm_array = np.array((max,min))
    np.savetxt('max_min_' + name + '.txt',mm_array)
    return


def cylinder(name, time, pi_fr = (2./3.), step = 0.5 ,path = None, skip = 1):
    """
        
    Cylinder
    This function contains the cylinder format
    
    Inputs
        name: variable name to be imported (string)
        time: End time slice to be converted (int) , if -1 entire dataset is imported
        pi_fr: Fraction of rotation of the cylinder, float between 0 and 2, 2./3. default option, 
        step: The gap between the y slices for the y interpolation (float < 1) if 0 then raw data displayed.
        path: File path to data, if blank then the current working directory is used to look for data
        
    Outputs
        Timestamped vtk files of the specified variable.
        A text file with the maximum and minimum files.


    """    
    
    #Get the working dir
    if path == None:
        work_dir = os.getcwd()
    if path != None:
        work_dir = os.chdir(path)
        work_dir = os.getcwd()
    
    # Get the grid file name
    grid_file = visual.get("BOUT.inp","grid")

    # Find dimensions of data
    max_t, var_0, nx, ny, nz = visual.dim_all(name)
    ny_work = ny
    # Import coordinates from gridfile
    r = visual.nc_var(grid_file,'Rxy') # toroidal coordinates
    z = visual.nc_var(grid_file,'Zxy') # toroidal coordinates
        
    #Interpolate setup
    #Get number of new points
    if step != 0:
        ny_work = len(np.arange(0,(ny-1),step))
        r2 = visual.intrp_grd(ny,r,ny_work,step)
        z2 = visual.intrp_grd(ny,z,ny_work,step)
        r = r2
        z = z2
    #Define empty array with increased number of y values
    var_new = np.empty((nx,ny_work,nz),dtype=float)
    pts = visual.cylinder(r, z, nx, ny_work, nz, pi_fr) # vtk grid points
    
    #Set time from input
    t = time
    
    # Set t to max_t, if user desires entire dataset
    if t == -1:
        t = max_t
    #If t is outside time dim of data set to max_t
    if t >= max_t:
        t = max_t
    
    ### Make dir for storing vtk files and image files
    #Check if dir for storing vtk files exsists if not make that dir
    if not os.path.exists("batch"):
        os.makedirs("batch")
    #Make dir for storing images
    if not os.path.exists("images"):
        os.makedirs("images")
    
    #Initial max and min values
    var_x, var_y, var_z = var_0[:,0,0], var_0[0,:,0], var_0[0,0,:]
    max_x, max_y, max_z = np.amax(var_x), np.amax(var_y), np.amax(var_z)
    min_x, min_y, min_z = np.amin(var_x), np.amin(var_y),np.amin(var_z)
    max = np.amax((max_x, max_y, max_z))
    min = np.amin((min_x, min_y, min_z))
    
    q = 0
    #For the entire t range import the spacial values, find min max values, interpolate y, coordinate transform, write to vtk
    while q <= t-1:
            var = visual.var3d(name,q) # collect variable
    
            #Find the min and max values
            var_x, var_y, var_z = var[:,0,0], var[0,:,0], var[0,0,:]
            max_x, max_y, max_z = np.amax(var_x), np.amax(var_y), np.amax(var_z)
            min_x, min_y, min_z = np.amin(var_x), np.amin(var_y), np.amin(var_z)
            max_i = np.amax(np.array((max_x,max_y,max_z)))
            min_i = np.amin(np.array((min_x,min_y,min_z)))
            if max_i >= max:
                    max = max_i
            if min_i <= min:
                    min = min_i
            
            if ny != ny_work: #Interpolate section for all y values
                for i in range(nx):
                    for k in range(nz):
                            var_y = var[i,:,k]
                            y = np.arange(0,ny) # Arrange y values in array
                            f = interpolate.interp1d(y,var_y) # Interpolate the data
                            y_new = np.arange(0,(ny-1),step) # Arrange new y values 
                            var_y_new = f(y_new) # interpolate y values
                            var_new[i,:,k] = var_y_new # Store values in new variable
            else:
                var_new = var
            #Convert coordinate section        
            vrbl = visual.vtk_var(var_new,nx,ny_work,nz) # vtk variable
            vtk_path = visual.write_vtk(name,pts,vrbl,q) # write vtk file
            print "At t = %d, %d Steps remaining" % (q,((t- q)/skip)) # Progress indicator
    
    #Write the Max and min values to file
    mm_array = np.array((max,min))
    np.savetxt('max_min_' + name + '.txt',mm_array)
    return
    
#==============================================================================
# Single Time slice converting functions 
#==============================================================================

def elm_t(name ,time ,zShf_int_p = 0.25, path = None):
    
    """
    elm_t
    The function elm_t converts a specified time slice and returns the mesh and variable
    
    Inputs
        name: variable name imported from BOUT.dmp files
        time: The end time slice that will be converted, if -1 entire dataset is imported
        zShift Interpolation Percentage: This is used to set the tolerance values for the linear interpolation.
        path: File path to data, if blank then the current working directory is used to look for data
    
    Outputs
        Returns the converted variable and the mesh
        
    """
    zShf_int_p = visual.zShf_p_check(zShf_int_p)

    # Get the working dir
    if path == None:
        work_dir = os.getcwd()
    if path != None:
        work_dir = os.chdir(path)
        work_dir = os.getcwd()
    
    grid_file = visual.get("BOUT.inp","grid") # Import grid file name 

    # Get the dimensions and initial value of the variable data.    
    max_t, var_0, nx, ny, nz = visual.dim_all(name)
      
    # ELM
    # Import r,z and zshift from grid file
    r = visual.nc_var(grid_file,'Rxy') # ELM Coordinates
    z = visual.nc_var(grid_file,'Zxy') # ELM Coordinates
    zshift = visual.nc_var(grid_file,'zShift') #ELM Coordinates
    
    max_z,min_z = visual.z_shift_mm(nx,ny,zshift) #Find the max and minimum zshift values
    z_tol = min_z + ((max_z - min_z) * zShf_int_p) # Set tolerance value
    
    # Interpolate the Rxy and Zxy values
    r2,ny2 = visual.zshift_interp2d(nx,ny,zshift,z_tol,r)
    z2,ny2 = visual.zshift_interp2d(nx,ny,zshift,z_tol,z)
    zshift2,ny2 = visual.zshift_interp2d(nx,ny,zshift,z_tol,zshift)
    
    # Create points for ELM 
    pts = visual.elm(r2,z2,zshift2,nx,ny2,nz)
    
    ## Set time
    t = time
    # Set t to max_t, if user desires entire dataset
    if t == -1:
        t = max_t
    #If t is greater than number of slices then set to max_t
    if t >= max_t:
        t = max_t
    
     # For a specific t slice import the spacial values, find min max values, interpolate y, coordinate transform, write to vtk
    var = visual.var3d(name,t) # collect variable
    var2,ny3 = visual.zshift_interp3d(nx,ny,nz,zshift,z_tol,var) # Interpolate Variable
    # Convert coordinate section
    vrbl = visual.vtk_var(var2,nx,ny2,nz) # vtk variable

    return vrbl,pts

def torus_t(name, time, step = 0.5, path = None, R = None, r = None , dr = None , Bt = None, q = None):
    """

    torus_t
    The function torus_t converts a specified time slice and returns the mesh and variable
    
    Inputs
        name: variable name imported from BOUT.dmp files
        time: The end time slice that will be converted, if -1 entire dataset is imported
        step: The gap between the y slices for the y interpolation (float < 1) if 0 then raw data displayed.
        path: File path to data, if blank then the current working directory is used to look for data
        
        Torus settings, if left blank defaults are used all are floats.
        R: Major radius
        r: Minor radius
        dr: Radial width of domain
        Bt: Toroidal magnetic field
        q: Safety factor
    
    Outputs
        Returns the converted variable and the mesh
    """
    
    # Get the working dir
    if path == None:
        work_dir = os.getcwd()
    if path != None:
        work_dir = os.chdir(path)
        work_dir = os.getcwd() 
    
    # Find the max_t, initial value and shape of variable
    max_t, var_0, nx, ny, nz = visual.dim_all(name)
    ny_work = ny
    
    # Interpolate setup
    # Get number of new points
    if step != 0:
        ny_work = len(np.arange(0,(ny-1),step))
    # Define empty array with increased number of y values
    var_new = np.empty((nx,ny_work,nz),dtype=float)
    
    #  ISTTOK specifications        R,r,dr,Bt,q = 0.46, 0.085, 0.02, 0.5, 5
    # Import coordinates from function in circle library
    r,z = circle.coordinates(nx,ny_work,nz,R,r,dr,Bt,q) # toroidal coordinates
    pts = visual.torus(r, z, nx, ny_work, nz)  # vtk grid points
    
    # Set time
    t = time
    # Set t to max_t, if user desires entire dataset
    if t == -1:
        t = max_t
    # If t is greater than number of slices then set to max_t
    if t >= max_t:
        t = max_t
    
    # For a specific t import the spacial values, find min max values, interpolate y, coordinate transform, write to vtk
    var = visual.var3d(name,t) # collect variable
    
    if ny != ny_work: # Interpolate section for all y values
        for i in range(nx):
            for k in range(nz):
                var_y = var[i,:,k]
                y = np.arange(0,ny) # Arrange y values in array
                f = interpolate.interp1d(y,var_y) # Interpolate the data
                y_new = np.arange(0,(ny-1),step) # Arrange new y values 
                var_y_new = f(y_new) # interpolate y values
                var_new[i,:,k] = var_y_new # Store values in new variable
    else:
        var_new = var
        # Convert coordinate section        
    vrbl = visual.vtk_var(var_new,nx,ny_work,nz) # vtk variable

    return vrbl,pts


def cylinder_t(name, time, pi_fr = (2./3.), step = 0.5, path = None):
    """

    cylinder_t
    The function cylinder_t converts a specified time slice to cylinderical geometry and returns the variable and mesh
    
    Inputs
        name: variable name imported from BOUT.dmp files
        time: The end time slice that will be converted, if -1 entire dataset is imported
        pi_fr:
        path: File path to data, if blank then the current working directory is used to look for data
    
    Outputs
        Returns the converted variable and the mesh
    """    
    
    # Get the working dir
    if path == None:
        work_dir = os.getcwd()
    if path != None:
        work_dir = os.chdir(path)
        work_dir = os.getcwd()
    
    # Get the grid file name
    grid_file = visual.get("BOUT.inp","grid")

    # Find dimensions of data
    max_t, var_0, nx, ny, nz = visual.dim_all(name)
    ny_work = ny
    # Import coordinates from gridfile
    r = visual.nc_var(grid_file,'Rxy') # toroidal coordinates
    z = visual.nc_var(grid_file,'Zxy') # toroidal coordinates
        
    # Interpolate setup
    # Get number of new points
    if step != 0:
        ny_work = len(np.arange(0,(ny-1),step))
        r2 = visual.intrp_grd(ny,r,ny_work,step)
        z2 = visual.intrp_grd(ny,z,ny_work,step)
        r = r2
        z = z2
    # Define empty array with increased number of y values
    var_new = np.empty((nx,ny_work,nz),dtype=float)
    pts = visual.cylinder(r, z, nx, ny_work, nz, pi_fr) # vtk grid points
    
    # et time from input
    t = time
    
    # Set t to max_t, if user desires entire dataset
    if t == -1:
        t = max_t
    # If t is outside time dim of data set to max_t
    if t >= max_t:
        t = max_t
    
    # For the entire t range import the spacial values, find min max values, interpolate y, coordinate transform, write to vtk
    var = visual.var3d(name,t) # collect variable

    
    if ny != ny_work: # Interpolate section for all y values
        for i in range(nx):
            for k in range(nz):
                    var_y = var[i,:,k]
                    y = np.arange(0,ny) # Arrange y values in array
                    f = interpolate.interp1d(y,var_y) # Interpolate the data
                    y_new = np.arange(0,(ny-1),step) # Arrange new y values 
                    var_y_new = f(y_new) # interpolate y values
                    var_new[i,:,k] = var_y_new # Store values in new variable
    else:
        var_new = var
    # Convert coordinate section        
    vrbl = visual.vtk_var(var_new,nx,ny_work,nz) # vtk variable

    return vrbl,pts    # Return the variable and mesh