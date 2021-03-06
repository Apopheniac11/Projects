# -*- coding: utf-8 -*-
"""EMEA_GCP Cluster Project - Data Preparation

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1qXkpBI9TkfpTBtqiU4m25Fxg3pyzevzc

# **Import Statements and File Loading**

You must run the code blocks to generate the key to authorize the GDrive download
"""

#Pip installs
# %%capture
!pip install -U ggplot

#Import required libraries
from __future__ import print_function
import pandas as pd
import numpy as np
import pylab as pl
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import pyplot
from mpl_toolkits.mplot3d import Axes3D
from sklearn import cross_validation
from sklearn import preprocessing
from sklearn.cluster import KMeans
from sklearn.cross_validation import  train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.decomposition import PCA
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, precision_score
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import Imputer
from sklearn.mixture import GMM
from ggplot import *
from sklearn.manifold import TSNE
import seaborn as sns
import statsmodels.api as sm
import datetime
import collections
import re

#User Authentication

from google.colab import auth
auth.authenticate_user()

from googleapiclient.discovery import build
drive_service = build('drive', 'v3')

# %matplotlib inline

#Importing csv file which is the source for this data analysis
file_id = '1usqov6yphZvQzPHQvIJyglFBwoO2OG6A' #File ID of CSV on Google Drive

import io
from googleapiclient.http import MediaIoBaseDownload

request = drive_service.files().get_media(fileId=file_id)
downloaded = io.BytesIO()
downloader = MediaIoBaseDownload(downloaded, request)
done = False
while done is False:
    # _ is a placeholder for a progress object that we ignore.
    _, done = downloader.next_chunk()

downloaded.seek(0)
print('Downloaded file contents are done.')

df_load = pd.read_csv(downloaded) #TODO: Import mixed types correctly
#print(df_load.dtypes)

"""# Helper Functions

### Dummy Creation Function
"""

# function that returns a dummified DataFrame of significant dummies in a given column
# This can help us reduce the dimensionality by creating dummy columns for only the most popular categories in a column

def dum_sign(dummy_col, threshold=0.1):

    # removes the bind
    dummy_col = dummy_col.copy()

    # what is the ratio of a dummy in whole column
    count = pd.value_counts(dummy_col) / len(dummy_col)

    # cond whether the ratios is higher than the threshold
    mask = dummy_col.isin(count[count > threshold].index)

    # replace the ones which ratio is lower than the threshold by a special name
    dummy_col[~mask] = "others"

    return pd.get_dummies(dummy_col, prefix=dummy_col.name)

  
   
    
#US 1987 SIC 1 is variable which defines the industry - https://www.census.gov/prod/techdoc/cbp/cbp96/sic-code.pdf
#The function below decodes the industry value using the information from the above link

def sic_to_indus(code):
  
    if str(code)[:2] in ['07','08','09']:
        return 'Agr_Fish_For'
      
    elif str(code)[:2] in ['10','12','13','14']:
        return 'Mining'
      
    elif str(code)[:2] in ['15','16','17']:
        return 'Construction'
      
    elif str(code)[:2] in ['20','21','22','23','24','25','26','27','28','29','30','31','32','33','34','35','36','37','38','39']:
        return 'Manufacturing'
      
    elif str(code)[:2] in ['41','42','44','45','46','47','48','49']:
        return 'Transport'
      
    elif str(code)[:2] in ['50','51']:
        return 'Wholesale Trade'
      
    elif str(code)[:2] in ['52','53','54','55','56','57','58','59']:
        return 'Retail Trade'
      
    elif str(code)[:2] in ['60','61','62','63','64','65','67']:
        return 'Fin_Ins_RE'
      
    elif str(code)[:2] in ['70','72','73','75','76','78','79','80','81','82','83','84','86','87','89']:
        return 'Services'
    else:
        return 'Unclassified'

"""# Data Cleaning and Manipulation

## Removing Unecessary Columns

Filter dataset down to EMEA region only
"""

#For this first analysis only perform the clustering on accounts from the AMER region
#We will go back through and run the other regions seperately
df = df_load.loc[df_load['region'] == 'EMEA']

#Show the number of rows and columns remaining after selecting only AMER
#This cuts the dataset roughly in half
df.shape

#Remove outliers that end up creating their own clusters and therefore not valuable to the analysis
#For example, in the EMEA region we found that Wordpress.com and Wordpress.org were creating their own cluster
outlier_list = []

df = df.drop(df[df['unique_code'].isin(outlier_list)].index)
df.shape

#Identify column names with GCP as part of the string. These columns are not part of the original domain feature space and would lead to to overfitting

#create a list of all existing columns
list_cols = df.columns.tolist()

#Scan through each column name to see if it contains GCP

for col in list_cols:
  if bool(re.search('GCP',col)):
    print (col)
    
## We are already removing all GCP related columns

#Check if the state variable needs any transformation to regions.The states which occur once can be treated as outliers

vc=df['State'].value_counts() 

#Creating a list to find out states which occur only once

states_2 =vc[vc>1].index.tolist()

#Filter records with states in list created above

df=df[df['State'].isin(states_2)]

df.shape

#Save the important columns so we can append them later and link back to the original records
saved_cols = df[['Respondents','unique_code','Domain','GCP_NA_Score','GCP_NA_Rating','GCP_EMEA_Score','GCP_EMEA_Rating','GCP_APAC_Score','GCP_APAC_Rating','opp_stage_name',\
                 'pipeline','region']]

#Remove all the unnecessary columns that will negatively affect the analysis
df = df.drop(['Respondents','unique_code','Slug', 'Domain','Parent Domain','Parent Slug','Website_LDC_Domain',\
                      'Intricately URL','Company Name','Website','LinkedIn URL','City/Region2',\
                      'State/Region1','Country','Country.1','Description','Company Name_LDC_Name','State',\
                      'Postal Code','Website_LDC_Domain','Unnamed: 80','Country_LDC_Country',\
                      'GCP_NA_Score','GCP_NA_Rating','GCP_EMEA_Score','GCP_EMEA_Rating','GCP_APAC_Score','GCP_APAC_Rating',\
                      'Unnamed: 160','Unnamed: 161','Unnamed: 155','opp_stage_name','pipeline','region'], axis=1)

saved_cols.shape

#Dealing with Missing Values.Columns with missing values

#Create a copy of the existing  dataframe before making changes
df_nas = df

"""## Handle SaaS Providers"""

#SaaS Providers - By examining some records it can be observed that the count of unique values for this variable is pretty high.
#Hence,we can create a new variable which stores the number of SaaS Providers 

df_nas['Count of SaaS Providers']= df_nas['SaaS Providers'].apply(lambda x: len(str(x).split(';')))

#SaaS providers - An list of unique SaaS providers can be generated and it can be converted into a dummy variable

#Create a empty list to store dns names
saas_provider_lst=[]

#Loop each string in DNS provider column and split using ';' to identify individual dns providers
for i in df_nas.index.tolist():
    try:
        saas_provider_lst.extend(df_nas.loc[i,'SaaS Providers'].split(';'))
    except:
        pass

#check the number of unique list of Saas providers
saas_uni = list(set(saas_provider_lst))
len(saas_uni)

#Extract the count for each saas provider
saas_dict = {}
for i in saas_uni:
    saas_dict[i]= saas_provider_lst.count(i)

#Filter SaaS providers with more than 15000 occurences across the data set
saas_fin=[]
for i in saas_dict:
    if saas_dict[i] > 10000:
        saas_fin.append(i.strip())

#Verify the records in saas_fin  
print(saas_fin)

#Create dummy variable to indicate the presence of SaaS provider (One hot encoding done manually)
for i in saas_fin:
    df_nas[i]=df_nas['SaaS Providers'][df_nas['SaaS Providers'].notnull()].apply(lambda x : 1 if i in x else 0)

"""## Handle DNS Providers"""

#DNS providers - An list of unique DNS providers can be generated and it can be converted into a dummy variable

#Create a empty list to store dns names
dns_provider_lst=[]

#Loop each string in DNS provider column and split using ';' to identify individual dns providers
for i in df_nas.index.tolist():
    try:
        dns_provider_lst.extend(df_nas.loc[i,'DNS Providers'].split(';'))
    except:
        pass

#check the number of unique list of dns providers
dns_uni = list(set(dns_provider_lst))
len(dns_uni)

#Extract the count for each dns provider
dns_dict = {}
for i in dns_uni:
    dns_dict[i]= dns_provider_lst.count(i)

#Filter DNS providers with more than 50 occurences across the data set
dns_fin=[]
for i in dns_dict:
    if dns_dict[i] > 50:
        dns_fin.append(i.strip())

len(set(dns_fin))

#Create dummy variable to indicate the presence of DNS provider (One hot encoding done manually)
for i in dns_fin:
    df_nas[i]=df_nas['DNS Providers'][df_nas['DNS Providers'].notnull()].apply(lambda x : 1 if i in x else 0)

#Create a new variable to store the decode industry from the sic code
df_nas['sic_industry'] =df_nas['US 1987 SIC 1'].apply(lambda x : sic_to_indus(x))

#By comparing the new column 'sic_industry' with 'Industry_LDC_PrimaryIndustry' and 'Line of Business' 
#it can be observed that both are very similar as they identify the industry
#Hence,we can use one of them - Industry_LDC_PrimaryIndustry
df_nas[['Industry_LDC_PrimaryIndustry','sic_industry','Line of Business']].head(10)

#Employee Range v value needs to be cleansed


#Check for any values which are not correct
df_nas['Employee Range'].value_counts()

#Some values needs transformations  10-Jan --> 1-10 ,Nov-50 --> 11-50

ind1=df_nas['Employee Range']=='10-Jan'
df_nas.ix[ind1,'Employee Range']='1-10'


ind2=df_nas['Employee Range']=='Nov-50'
df_nas.ix[ind2,'Employee Range']='11-50'

##Some rows have values 0 and 0.0 .Replace 0.0 with 0

ind3=df_nas['Employee Range']=='0.00'
df_nas.ix[ind3,'Employee Range']='0'

##Some rows have values 43110.00  and 18568.00 .Replace these with >10000

ind4=df_nas['Employee Range']=='18568.00'
df_nas.ix[ind4,'Employee Range']='>10,000'


ind5=df_nas['Employee Range']=='43110.00'
df_nas.ix[ind5,'Employee Range']='>10,000'

#Confirm the updates 
df_nas['Employee Range'].value_counts()

#Drop columns - 'sic_industry','Line of Business','Industry','Hosting Providers' ,'DNS Providers','SaaS Providers','US 1987 SIC 1' as we have 
#already use their info
df_nas.drop(['sic_industry','Line of Business','Industry','Hosting Providers' ,'DNS Providers','SaaS Providers','US 1987 SIC 1','Google Cloud Platform'], axis=1, inplace=True)

"""### Keep a copy of the original dataframe before standardization to be merged with results for final analysis"""

#Create a copy of the dataframe in its current form befor standardization .This will be required to use actual values during cluster analysis
df_org =df_nas

df_org.shape

"""## Create Dummy Variables for Categorical Columns

Some of the categorical columns contain many categories, because of this we need to only create dummies for the highest frequency results for each categorical column, otherwise the dataset will become too wide

### Loop through all category columns and create dummies
"""

#List of categorical column names that we need to create dummy columns for:
#I went through the CSV and looked at each column, this should be the full list
cat_list = ['Monthly Spend Total', 'Primary Hosting Provider', 'Primary Hosting Provider Monthly Spend',\
            'Secondary Hosting Provider','Secondary Hosting Provider Monthly Spend',\
            'Hosting Monthly Spend','Primary Security Provider','Primary Security Provider Monthly Spend',\
            'Security Providers','Security Monthly Spend','Primary CDN (Content Delivery) Provider',\
            'Primary CDN (Content Delivery) Provider Monthly Spend','Secondary CDN (Content Delivery) Provider',\
            'Secondary CDN (Content Delivery) Provider Monthly Spend','CDN (Content Delivery) Providers',\
            'CDN (Content Delivery) Monthly Spend','Primary DNS Provider','Primary DNS Provider Monthly Spend',\
            'Secondary DNS Provider','Secondary DNS Provider Monthly Spend','DNS Monthly Spend',\
            'Primary GTM (Traffic Management) Provider','Primary GTM (Traffic Management) Provider Monthly Spend',\
            'GTM (Traffic Management) Providers','GTM (Traffic Management) Monthly Spend','OVP (Video Platform) Providers',\
            'APM (Performance Management) Providers','Configuration','Sophistication','Hybrid Applications',\
            'Agile Tools','Cloud Applications','Enterprise Application Security','Has Azure','Hybrid IT',\
            'Predictive Analytics','Mobile Application Management',	'Containers',	'Machine Learning',	'Distributed Denial-of-Service (DDoS)',\
            'Has Microsoft OneDrive','Phishing','Data Security','Has VMware Mobile Virtualization Platform',\
            'Big Data Analytics','Industry_LDC_PrimaryIndustry','Ransomware','Data Lake','Cloud Orchestration','Has Amazon AWS CloudFormation',\
            'Amazon Redshift','Cloud Computing','Data Theft','Cloud Security','Cloud Infrastructure',\
            'Hybrid Cloud','Data Encryption','Has IBM SmartCloud Enterprise','Hybrid IT Environments','Has VMware vCloud',\
            'Has Amazon SimpleDB','Azure Data Lake','Cloud IDE','Containerization','Data Visualization','Has Amazon EC2','App Development',\
            'Has HP Thin Client Hardware','Cloud Backup / Recovery',\
            'Cloud Strategy','Cloud Provisioning','Security Monitoring','Has Microsoft Office 2013','Has Citrix CloudPlatform',\
            'Penetration Testing','Cloud Storage','Marketing Analytics','Revenue Range','API Management','Employee Range','Employees',\
            'Internet of Things (IoT)'
           ]

#Loop through the categorical column names
#run each column through the dum_sign function
#append the results back to our dataframe to send to PCA
for column in cat_list:
        dummy_cols = dum_sign(df_nas[column], threshold=0.03)
        df_nas = pd.concat([df_nas, dummy_cols], axis=1)
        df_nas = df_nas.drop(column, axis=1)

df_nas.shape


list(df_nas)

##Save a copy of the dataframe -df_nas which contains all features pre-normalization
df_copy_nas=df_nas

#Preprocess and standardize the data
#Remove any random strings throughout the dataset and convert them to NaN
df_nas.apply(pd.to_numeric, errors='coerce')

#Input the NaN values to the mean
fill_NaN = Imputer(missing_values=np.nan, strategy='mean', axis=1)
df_nas = pd.DataFrame(fill_NaN.fit_transform(df_nas), columns=df_nas.columns)

#Scale the dataset using the standard scaler, 0 = mean
df_nas = pd.DataFrame(StandardScaler().fit_transform(df_nas), columns=df_nas.columns)
df_nas.head()

"""# Principal Component Analysis

## Creating PCAs with 2 and 3 components which we will use to plot the results of our clustering
"""

#Use PCA to reduce dimensionality
'''
pca = PCA(.99) #retain 99% of the variance 
df_reduced = pd.DataFrame(pca.fit_transform(df_nas))
df_reduced.head()
'''
#We found that the reduced dimensionality did not improve the clustering
#Therefore we are retaining all of the columns for the clustering algorithms
df_reduced = df_nas

#Creating a PCA dataframe with 2 features for plotting later
pca = PCA(n_components=2) #retain 2 components only 
df_pca_2 = pd.DataFrame(pca.fit_transform(df_nas))
df_pca_2.head()

#Creating a PCA dataframe with 3 features for plotting later
pca = PCA(n_components=3) #retain 3 components only 
df_pca_3 = pd.DataFrame(pca.fit_transform(df_nas))
df_pca_3.head()

#Creating a PCA dataframe with 4 features for plotting later
pca = PCA(n_components=4) #retain 3 components only 
df_pca_4 = pd.DataFrame(pca.fit_transform(df_nas))
df_pca_4.head()

"""## Checking the cumulative variance explained by N components"""

#Checking variances explained based on the number of components
#Starting with random value of 100
pca = PCA(n_components=100) 
pca.fit(df_nas)
var = pca.explained_variance_ratio_

#Cumulative Variance explains
var1 = np.cumsum(np.round(pca.explained_variance_ratio_, decimals=4)*100)
#From this plot we can observe that the number of components required to explain around 80% of the variance will be 50

#plt.plot(var1)
#print ('Combined  variation for 50 principal components: {}' .format((np.sum(pca.explained_variance_ratio_))))

#Based on the above plot performing pca with 50 components
pca = PCA(n_components=50)
pca.fit(df_nas)
df_pca_50=pd.DataFrame(pca.fit_transform(df_nas))

##In the following steps- I have tried out clustering based on tsne. Since, we are using 50 components ,tsne would enable us to
##plot components in 2 dimensional space

##Making a list of columns in the current df_pca_50 df as we would be need in te later steps
fin_cols=df_pca_50.columns.tolist()

#Reset indices for df_nas and saved_cols 
saved_cols = saved_cols.reset_index(drop=True)

##Adding the columns 'Respondents' and 'GCP_NA_Rating' to dataframe we can use them to identify clusters
df_pca_50['Respondents']= saved_cols['Respondents']

df_pca_50['GCP_NA_Rating'] = saved_cols['GCP_NA_Rating']

##Check distribution of Respondents and GCP_NA_Ratings
df_pca_50['GCP_NA_Rating'].value_counts()

df_pca_50['Respondents'].value_counts()

"""## TSNE for Visualization (Commented Out because of long runtime)"""

##Running the TSNE algorithn
#TSNE is very time consuming and hence using stratified sample of 50% 
#X_train, X_test = train_test_split(df_pca_50, test_size=0.50, random_state=42,stratify=df_pca_50['Respondents'])

##Use X_test to run tsne
#tsne = TSNE(n_components=2, verbose=1, perplexity=40, n_iter=300)
#tsne_pca_results = tsne.fit_transform(X_test[fin_cols])

#df_tsne=None
#df_tsne = X_test.copy()
#df_tsne['x-tsne'] = tsne_pca_results[:,0]
#df_tsne['y-tsne'] = tsne_pca_results[:,1]

##Plot using ggplot

##Respondents
#chart = ggplot( df_tsne, aes(x='x-tsne', y='y-tsne',color='Respondents' ) )\
#        + geom_point(size=70,alpha=0.1)

#chart
#There are some areas in the chart below where blue (Respondent = 1) is dominant

##Plot using ggplot

#chart = ggplot( df_tsne, aes(x='x-tsne', y='y-tsne',color='GCP_NA_Rating' ) )\
#        + geom_point(size=70,alpha=0.1)

#chart
#Not sure about the definition of GCP_NA_Rating.I think ratings A and B may be good and they are mostly located near the center

"""Trying the Elbow Method first to determine the optiminal number of clusters

*   We run KMeans through a loop 20 times and calculate the cumulative error
*   We then plot this to see at what number of clusters we stop explaining large portions of variance
*   From this test it appears to be 5, but this is influenced by choices made in the PCA step
"""

'''
cluster_range = range( 1, 20 )
cluster_errors = []

for num_clusters in cluster_range:
    clusters = KMeans(num_clusters)
    clusters.fit(df_reduced)
    cluster_errors.append(clusters.inertia_)

clusters_df = pd.DataFrame({"num_clusters":cluster_range,"cluster_errors":cluster_errors})
clusters_df[0:10]
'''

#plt.figure(figsize=(12,6))
#plt.plot(clusters_df.num_clusters, clusters_df.cluster_errors, marker="o")

"""TODO: Sillouette Test to Compare cluster choice

# Save DataFrames To File

This section saves to the Google Drive all of the dataframes that we have constructed<br>
allowing us to later re-train the models without having to rebuild the dataframes from scratch
<br><b>This code will overwrite existing files and create new file IDs!
"""

!pip install -U -q PyDrive

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from google.colab import auth
from oauth2client.client import GoogleCredentials

#Authenticate and create the PyDrive client.
auth.authenticate_user()
gauth = GoogleAuth()
gauth.credentials = GoogleCredentials.get_application_default()
drive = GoogleDrive(gauth)

#Create pickle files on the CoLaboratory VM
df_nas.to_pickle('df_nas.pkl')
df_pca_2.to_pickle('df_pca_2.pkl')
df_pca_3.to_pickle('df_pca_3.pkl')
df_pca_4.to_pickle('df_pca_4.pkl')
saved_cols.to_pickle('saved_cols.pkl')
df_org.to_pickle('df_org.pkl')
df_copy_nas.to_pickle('df_copy_nas.pkl')

#Shared EMEA folder in Data Science folder ID: 1pSJZgJ4LJp6VcRk68_mkPWxyMsUXoAF2
#fid = '1ak0Jcz2Hx_tytApiQncr8hXUfKyWc3CI'
fid = '1pSJZgJ4LJp6VcRk68_mkPWxyMsUXoAF2'
file_list = drive.ListFile({'q': "'%s' in parents and trashed=false" % fid}).GetList()
files_to_upload = ['df_nas.pkl','df_pca_2.pkl','df_pca_3.pkl','saved_cols.pkl','df_org.pkl','df_copy_nas.pkl']


def delete_existing_file(file_name,file_list):
    for file1 in file_list:
        if file1['title'] == file_name:
            file1.Delete() 
            
def upload_to_drive(file_name,file_list,folder_id):
    uploaded = drive.CreateFile({'title': file_name, "parents": [{"kind": "drive#fileLink", "id": folder_id}]})
    uploaded.SetContentFile(file_name)
    uploaded.Upload()
    print('Uploaded %s with ID {}'.format(uploaded.get('id')) % file_name)
    
#Upload each file
for file in files_to_upload:
    delete_existing_file(file, file_list) 
    upload_to_drive(file,file_list,fid)