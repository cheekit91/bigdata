from bs4 import BeautifulSoup
import urllib.request
import re

def convertInt(input):
    return int(re.sub("[^\d\.]", "", input)) #remove commas

def getCompetitorInfo(ticker):
    competitorName=[]
    try:
        html_page = urllib.request.urlopen("https://www.nasdaq.com/symbol/%s/competitors"%ticker.lower())
        soup = BeautifulSoup(html_page,"html.parser")
        lastPageInfo=soup.find("a",{"id":"quotes_content_left_lb_LastPage"})
        if(lastPageInfo==None): #if there is no second page
            lastPage=1
        else:
            lastPage=int(lastPageInfo.get('href').split('=')[-1])
        for i in range(lastPage): 
            html_page = urllib.request.urlopen("https://www.nasdaq.com/symbol/%s/competitors?page=%s"%(ticker.lower(),str(i+1)))
            soup = BeautifulSoup(html_page,"html.parser")
            competitors=soup.find("div", {"class": "genTable thin"})
            competitorNameRecords=competitors.findAll("td",{"class":"TalignL"})
            for name in competitorNameRecords:
                competitorName.append(name.get_text().split(':')[0])
    except:
        pass

    return competitorName

def getStakeHolderInfo(ticker):
    myDict={}
    stakeHoldersName=[]
    html_page = urllib.request.urlopen("https://www.nasdaq.com/symbol/%s/institutional-holdings"%ticker.lower())
    soup = BeautifulSoup(html_page,"html.parser")
    try:
        stakeholders=soup.find("div", {"id": "quotes_content_left_pnlInsider"})
        pred = lambda tag: tag.parent.find('thead')
        stakeHoldersRecords=filter(pred,stakeholders.findAll("tr"))
        totalStockInfo=soup.find("div",{"class":"header-tabs-div paddingT15px"})
        # print(totalStockInfo)
        totalNumberOfStocks=totalStockInfo.find("h4").find("span",id="quotes_content_left_totalheld").get_text().split(" Total Shares Held")[0]
        totalNumberOfStocks=convertInt(totalNumberOfStocks)
        for name in stakeHoldersRecords:
            records=name.findAll("td")
            myDict[records[0].find("a").get_text()]=convertInt(records[2].get_text())/totalNumberOfStocks
    except:
        pass

    return myDict

def getPersonalInfo(link):
    output=[]
    career=[]
    mbrship=[]
    html_page2 = urllib.request.urlopen("https://www.bloomberg.com/%s"%link)
    soup2 = BeautifulSoup(html_page2,"html.parser")

    careerhistory=soup2.find("div", {"class": "markets_module bio_career"})
    if(careerhistory!=None):
        careerRecords=careerhistory.findAll("li",{"class":"record"})
        careerRecords+=careerhistory.findAll("li",{"class":"last record"})
        careerRecords+=careerhistory.findAll("li",{"class":"hidden record"})
        careerRecords+=careerhistory.findAll("li",{"class":"hidden last record"})
        for record in careerRecords:
            career.append(record.findAll('span')[0].get_text()+','+record.findAll('span')[1].get_text())
        if(career[len(career)-1]==career[len(career)-2]): #check for duplicates
            del career[-1]
        output.append(career)
    else:
        output.append([])

    boardmembership=soup2.find("div", {"class": "board_memberships first section"})
    if(boardmembership!=None):
        companies=boardmembership.findAll("span",{"class":"company_name"})
        memberships=boardmembership.findAll("span",{"class":"byline"})
        for idx,company in enumerate(companies):
            mbrship.append(company.get_text().rstrip().lstrip()+','+memberships[idx].get_text().rstrip().lstrip())
        output.append(mbrship)
    else:
        output.append([])

    return output

def getCompanyExecutivesInfo(ticker):
    html_page = urllib.request.urlopen("https://www.bloomberg.com/quote/%s:US"%ticker)
    soup = BeautifulSoup(html_page,"html.parser")
    executives=soup.find("div", {"class": "executivesContainer__7f9fc250"})
    output=[]
    careerHistoryBoardMembership=[]

    allExecutivesName=getAllText(executives.findAll("div", {"class": "name__c96644d1"}))
    allExecutivesPosition=getAllText(executives.findAll("div", {"class": "title__cde0e39b"}))

    for link in executives.find_all('a'):
        careerHistoryBoardMembership.append(getPersonalInfo(link.get('href')))

    for idx in range(len(allExecutivesName)):
        temp=[]
        temp.append(allExecutivesName[idx])
        temp.append(allExecutivesPosition[idx])
        temp.append(careerHistoryBoardMembership[idx][0])
        temp.append(careerHistoryBoardMembership[idx][1])
        output.append(temp)

    return output

def getCompanyBoardInfo(ticker):
    html_page = urllib.request.urlopen("https://www.bloomberg.com/quote/%s:US"%ticker)
    soup = BeautifulSoup(html_page,"html.parser")
    board=soup.find("div", {"class": "boardContainer__c8751b40"})
    # print(board)
    output=[]
    careerHistoryBoardMembership=[]

    allBoardName=getAllText(board.findAll("div", {"class": "name__c96644d1"}))
    allBoardEmployer=getAllText(board.findAll("div", {"class": "company__7f8639ea"}))

    careerHistoryBoardMembership={}
    for idx in range(len(allBoardName)):
        careerHistoryBoardMembership[idx]=[]

    for link in board.find_all('a'):
        nameIdx=0
        for idx,name in enumerate(allBoardName):
            if(name==link.get('title')):
                nameIdx=idx
        careerHistoryBoardMembership[nameIdx]=getPersonalInfo(link.get('href'))

    for idx in range(len(allBoardName)):
        temp=[]
        temp.append(allBoardName[idx])
        temp.append(allBoardEmployer[idx])
        if(careerHistoryBoardMembership[idx]!=[]):
            temp.append(careerHistoryBoardMembership[idx][0])
            temp.append(careerHistoryBoardMembership[idx][1])
        else:
            temp.append([])
            temp.append([])

        output.append(temp)

    return output

def getAllText(inputData):
    output=[]
    for i in inputData:
        output.append(i.get_text())

    return output

def findTicker(inputString):
    inputString = ''.join([i for i in inputString if not i.isdigit()])
    inputString = re.sub(r"[^\w\s]", '', inputString) #remove all weird characters other than numbers and letters
    inputString.replace(" ","+") #replace all space to +
    html_page = urllib.request.urlopen("https://www.bloomberg.com/markets/symbolsearch?query=%s&commit=Find+Symbols"%inputString)
    soup = BeautifulSoup(html_page,"html.parser")
    firstTicker=soup.find("tr", {"class": "odd"})
    if(":US" in firstTicker.find("a").get_text()): #if stock is not in US
        tickerName=firstTicker.find("a").get_text().split(":US")[0]
        print("Rerouting to ticker %s"%tickerName)
    else:
        tickerName=None
        print("Search result not found")
    return tickerName

ticker=None
while(ticker==None):
    searchInput = input("Enter the company or ticker name that you are interested in: ")
    ticker=findTicker(searchInput)

stakeHolderDict=getStakeHolderInfo(ticker)
competitorRecords=getCompetitorInfo(ticker)
print('\nStakeHolders:')
print(stakeHolderDict)
print('\nCompetitorsInfo:')
print(competitorRecords)

print('\nBoardInfo:')
info=getCompanyBoardInfo(ticker)
for i in info:
    print(i)

print('\nExecutiveInfo:')
info=getCompanyExecutivesInfo(ticker)
for i in info:
    print(i)
