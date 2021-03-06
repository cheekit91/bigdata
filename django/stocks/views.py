from django.shortcuts import render
from .models import Stock
from .forms import StockForm
import json
import requests

from multiprocessing import Process,Manager, Value

from plotly.graph_objs import *
from plotly.offline import download_plotlyjs, init_notebook_mode, plot, iplot
import networkx as nx

from bs4 import BeautifulSoup
import urllib2
import re
import time
from threading import Thread

from py2neo import authenticate,Graph
from py2neo import Node, Relationship

def convertInt(input):
    return int(re.sub("[^\d\.]", "", input)) #remove commas

def getCompetitorInfo(ticker,tickerNameBB,competitorName,marketCap):
    try:
        html_page = urllib2.urlopen("https://www.nasdaq.com/symbol/%s/competitors"%ticker.lower())
        soup = BeautifulSoup(html_page,"html.parser")
        lastPageInfo=soup.find("a",{"id":"quotes_content_left_lb_LastPage"})
        header=soup.find("div", {"id": "qwidget_pageheader"})
        ownName=header.get_text().split(" Competitors")[0]
        if(lastPageInfo==None): #if there is no second page
            lastPage=1
        else:
            lastPage=int(lastPageInfo.get('href').split('=')[-1])
        for i in range(lastPage): 
            html_page = urllib2.urlopen("https://www.nasdaq.com/symbol/%s/competitors?page=%s"%(ticker.lower(),str(i+1)))
            soup = BeautifulSoup(html_page,"html.parser")
            competitors=soup.find("div", {"class": "genTable thin"})
            tableBody=competitors.find("tbody").findAll("tr")

            competitorNameRecords=competitors.findAll("td",{"class":"TalignL"})
            for idx,name in enumerate(competitorNameRecords):
                cName=name.get_text().split(name.find("a").get_text())[0]
                if(cName!=ownName and cName!=''):
                    marketCap.append(convertInt(tableBody[idx].findAll('td')[7].get_text()))
                    competitorName.append(cName)
                if(cName==ownName):
                    ownMarketCap=convertInt(tableBody[idx].findAll('td')[7].get_text())

        marketCap.insert(0,ownMarketCap)
    except:
        pass

    

def getStakeHolderInfo(ticker,tickerNameBB,stakeHoldersName,OverallPR):
    # stakeHoldersShare=[]
    # stakeHoldersShare=[]
    html_page = urllib2.urlopen("https://www.nasdaq.com/symbol/%s/institutional-holdings"%ticker.lower())
    soup = BeautifulSoup(html_page,"html.parser")
    lastPageInfo=soup.find("a",{"id":"quotes_content_left_lb_LastPage"})
    if(lastPageInfo==None): #if there is no second page
        lastPage=1
    else:
        lastPage=int(lastPageInfo.get('href').split('=')[-1])

    threads = []
    PROverLink=[]
    percentShares=[]
    idxRecord=0
    for i in range(lastPage): 
        html_page = urllib2.urlopen("https://www.nasdaq.com/symbol/%s/institutional-holdings?page=%s"%(ticker.lower(),str(i+1)))
        soup = BeautifulSoup(html_page,"html.parser")
        stakeholders=soup.find("div", {"id": "quotes_content_left_pnlInsider"})
        pred = lambda tag: tag.parent.find('thead')
        stakeHoldersRecords=filter(pred,stakeholders.findAll("tr"))
        totalStockInfo=soup.find("div",{"class":"header-tabs-div paddingT15px"})
        totalNumberOfStocks=totalStockInfo.find("h4").find("span",id="quotes_content_left_totalheld").get_text().split(" Total Shares Held")[0]
        totalNumberOfStocks=convertInt(totalNumberOfStocks)

        for idx,name in enumerate(stakeHoldersRecords):
            records=name.findAll("td")
            amountOfSharesHold=1.0/totalNumberOfStocks*convertInt(records[2].get_text())
            if(amountOfSharesHold<0.01):
                break
            percentShares.append(amountOfSharesHold)

            threads.append(None)
            PROverLink.append(None)
            a=records[0].find("a")
            link=a.get("href")
            threads[idx+idxRecord] = Thread(target=getInsitutionalInfo, args=(link,PROverLink,idx+idxRecord))
            threads[idx+idxRecord].start()

            stakeHoldersName.append(a.get_text())

        idxRecord=len(threads)
            # stakeHoldersShare.append(amountOfSharesHold)
        if(amountOfSharesHold<0.01):
            break
    
    for i in range(len(threads)):
        threads[i].join()

    for idx,shares in enumerate(percentShares):
        if(shares!=None):
            OverallPR.value+=PROverLink[idx]*shares


def getInsitutionalInfo(link,result,index):
    html_page = urllib2.urlopen(link)
    soup = BeautifulSoup(html_page,"html.parser")
    resultTable=soup.find("tr",{"id":"position-stats-results"})
    if(soup.findAll("td")[1]==None):
        result[index]=None
    else:
        result[index]=1.0/convertInt(soup.findAll("td")[1].get_text())*convertInt(resultTable.findAll("td")[-1].get_text())



def getPersonalInfo(link,result,index,tickerNameBB):
    output=[]
    career=[]
    mbrship=[]
    try:
        html_page2 = urllib2.urlopen("https://www.bloomberg.com/%s"%link)
        soup2 = BeautifulSoup(html_page2,"html.parser")
    
        careerhistory=soup2.find("div", {"class": "markets_module bio_career"})
        if(careerhistory!=None):
            careerRecords=careerhistory.findAll("li",{"class":"record"})
            careerRecords+=careerhistory.findAll("li",{"class":"last record"})
            careerRecords+=careerhistory.findAll("li",{"class":"hidden record"})
            careerRecords+=careerhistory.findAll("li",{"class":"hidden last record"})
            for record in careerRecords:
                if(tickerNameBB in record.findAll('span')[1].get_text()):
                    pass
                else:
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
                if(tickerNameBB in company.get_text().rstrip().lstrip()):
                    pass
                else:
                    mbrship.append(company.get_text().rstrip().lstrip()+','+memberships[idx].get_text().rstrip().lstrip())
            output.append(mbrship)
        else:
            output.append([])
        result[index]=output
    except:
        result[index]=[[],[]]

    # return output

def getCompanyKeyPersonnel(ticker):
    html_page = urllib2.urlopen("https://www.bloomberg.com/quote/%s:US"%ticker)
    soup = BeautifulSoup(html_page,"html.parser")
    body=soup.find("body")
    careerhistory=body.find("script", {"type": "text/javascript"}).get_text()
    menu = json.loads(re.search(r"window.__bloomberg__.bootstrapData\s*=\s*(.*);", careerhistory).group(1))
    url="https://www.bloomberg.com/markets2/api/peopleForCompany/%s"%menu['quote']['bbid']
    req = requests.get(url)
    people=json.loads(req.text)
    boardMembers=people['boardMembers']
    executives=people['executives']

    return executives,boardMembers
def getCompanyExecutivesInfo(executives,tickerNameBB,executivesInfo):
    allExecutivesName=[]
    allExecutivesPosition=[]
    allExecutivesLink=[]
    for i in executives:
        allExecutivesName.append(i['name'])
        allExecutivesPosition.append(i['title'])
        allExecutivesLink.append("profiles/people/%s"%i['id'])

    careerHistoryBoardMembership={}
    for idx in range(len(allExecutivesName)):
        careerHistoryBoardMembership[idx]=[]

    threads = [None] *len(allExecutivesName)

    for idx,link in enumerate(allExecutivesLink):
        threads[idx] = Thread(target=getPersonalInfo, args=(link,careerHistoryBoardMembership,idx,tickerNameBB))
        threads[idx].start()

    for i in range(len(threads)):
        threads[i].join()


    for idx in range(len(allExecutivesName)):
        temp=[]
        temp.append(allExecutivesName[idx])
        temp.append(allExecutivesPosition[idx])
        temp.append(careerHistoryBoardMembership[idx][0])
        temp.append(careerHistoryBoardMembership[idx][1])
        executivesInfo.append(temp)



def getCompanyBoardInfo(boardMembers,tickerNameBB,companyBoardInfo):
    allBoardName=[]
    allBoardEmployer=[]
    allBoardLink=[]
    for i in boardMembers:
        allBoardName.append(i['name'])
        allBoardEmployer.append(i['companyName'])
        allBoardLink.append("profiles/people/%s"%i['id'])
    careerHistoryBoardMembership={}
    for idx in range(len(allBoardName)):
        careerHistoryBoardMembership[idx]=[]

    threads = [None] *len(allBoardName)

    for index,link in enumerate(allBoardLink):
        if(allBoardEmployer[index]!=None):
            threads[index] = Thread(target=getPersonalInfo, args=(link,careerHistoryBoardMembership,index,tickerNameBB))
            threads[index].start()
        
    for i in range(len(threads)):
        if(threads[i]!=None):
            threads[i].join()
        
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

        companyBoardInfo.append(temp)


def getAllText(inputData):
    output=[]
    for i in inputData:
        output.append(i.get_text())

    return output

def findTicker(inputString):
    inputString = ''.join([i for i in inputString if not i.isdigit()])
    inputString = re.sub(r"[^\w\s]", '', inputString) #remove all weird characters other than numbers and letters
    inputString = inputString.replace(" ","+") #replace all space to +
    html_page = urllib2.urlopen("https://www.bloomberg.com/markets/symbolsearch?query=%s&commit=Find+Symbols"%inputString)
    soup = BeautifulSoup(html_page,"html.parser")
    tickerList=soup.findAll("tr", {"class": ["odd","even"]})
    for ticker in tickerList:
        if(":US" in ticker.find("a").get_text()): #if stock is not in US
            tickerName=ticker.find("a").get_text().split(":US")[0]
            print("Rerouting to ticker %s"%tickerName)
            return tickerName
    tickerName=None
    print("Search result not found")
    return tickerName

def findCompanyNameFromBloomberg(ticker):
    html_page = urllib2.urlopen("https://www.bloomberg.com/quote/%s:US"%ticker.lower())
    soup = BeautifulSoup(html_page,"html.parser")
    tickerName=soup.find("h1", {"class": "companyName__99a4824b"}).get_text()
    return tickerName

def produceGraph(tickerName,inputData,inputtype):
    G=nx.Graph()
    # # Add nodes by specifying their positions
    if(inputtype=="Competitor"):
        color="#FF0000"
    elif(inputtype=="StakeHolder"):
        color="008000"
    else:
        color="000000"
        
    graph = Graph()

    G.add_node(tickerName)
    if(inputtype=="Competitor" or inputtype=="StakeHolder"):   
        for competitorName in inputData:
            G.add_node(competitorName)
            G.add_edge(tickerName,competitorName,weight=1, label=inputtype)
            tx=graph.begin()
            tx.run("MATCH (n:%s {name:{b}}) CREATE (m:%s {name:{a}})-[:%s]->(n)"%("Company",inputtype+"Company",inputtype),
                           a=competitorName, b=tickerName)
            tx.commit()
    else:
        for data in inputData:
            personName=data[0]
            G.add_node(personName)
            G.add_edge(tickerName,personName,weight=1, label=inputtype) #position
            tx=graph.begin()
            tx.run("MATCH (n:%s {name:{b}}) CREATE (m:%s {name:{a}})-[:%s]->(n)"%("Company",inputtype,inputtype),
                           a=personName, b=tickerName)
            tx.commit()
            for careerHistory in data[2]:
                if(careerHistory!=[]):
                    array=careerHistory.split(',') #0-position,1-company name,2-duration
                    companyName=array[1]
                    if(companyName!=tickerName):
                        G.add_node(companyName)
                    if(len(array)>2):
                        inputlabel=inputtype+':'+array[0]+','+array[2]
                    else:
                        inputlabel=inputtype+':'+array[0]
                    G.add_edge(personName,companyName,weight=1, label=inputlabel)
                    tx=graph.begin()
                    tx.run("MATCH (m:%s {name:{b}}) CREATE (n:%s {name:{a}})-[:%s]->(m)"%(inputtype,"CompanyCareerHistory","CareerHistory"),
                                   a=companyName, b=personName)
                    tx.commit()

            for boardmembership in data[3]:
                if (boardmembership!=[]):
                    array=boardmembership.split(',') #0-company name,1-position,2-duration
                    # print(array)
                    companyName=array[0]
                    if(companyName!=tickerName):
                        G.add_node(companyName)
                    if(len(array)>2):
                        inputlabel=inputtype+':'+array[1]+','+array[2]
                    elif(len(array)==2):
                        inputlabel=inputtype+':'+array[1]
                    else:
                        inputlabel=inputtype
                    G.add_edge(personName,companyName,weight=1, label=inputlabel)
                    tx=graph.begin()
                    tx.run("MATCH (m:%s {name:{b}}) CREATE (n:%s {name:{a}})-[:%s]->(m)"%(inputtype,"CompanyBoardMembership","BoardMember"),
                                   a=companyName, b=personName)
                    tx.commit()

    div=printGraph(G,tickerName,inputtype)
    return G,div

def printGraph(G,tickerName,inputtype):
    # # Add nodes by specifying their positions
    pos = nx.spring_layout(G)
    figureData=[]
    dmin=1
    ncenter=0
    for n in pos:
        x,y=pos[n]
        d=(x-0.5)**2+(y-0.5)**2
        if d<dmin:
            ncenter=n
            dmin=d

    p=nx.single_source_shortest_path_length(G,ncenter)

    node_trace = Scatter(
        x=[],
        y=[],
        text=[],
        mode='markers+text',
        hoverinfo='text',
        textposition='top',
        marker=Marker(
            showscale=False,
            # colorscale options
            # 'Greys' | 'Greens' | 'Bluered' | 'Hot' | 'Picnic' | 'Portland' |
            # Jet' | 'RdBu' | 'Blackbody' | 'Earth' | 'Electric' | 'YIOrRd' | 'YIGnBu'
            colorscale='YIGnBu',
            reversescale=True,
            color=[],
            size=10,
            colorbar=dict(
                thickness=15,
                title='Node Connections',
                xanchor='left',
                titleside='right'
            ),
            line=dict(width=2)))

    for idx,node in enumerate(G.nodes()):
        x, y = pos[node]
        node_trace['x'].append(x)
        node_trace['y'].append(y)
        node_trace['text'].append(node)

    for node, adjacencies in enumerate(nx.generate_adjlist(G)):
        node_trace['marker']['color'].append(len(adjacencies))
    #     node_info ='# of connections: '+str(len(adjacencies))
    figureData.append(node_trace)

    if(inputtype=="Competitor"):
        color="#FF0000"
    elif(inputtype=="StakeHolder"):
        color="008000"
    else:
        color="000000"

    typeEnum=["Competitor","StakeHolder","BoardMember","Executive"]
    colorEnum=["#FF0000","008000","000000","000000"]
    for idx,typeinput in enumerate(typeEnum):
        edge_trace = Scatter(
            x=[],
            y=[],
            line=Line(width=0.5,color=colorEnum[idx]),
            hoverinfo='none',
            mode='lines')
        middle_node_trace = Scatter(
            x=[],
            y=[],
            text=[],
            mode='markers',
            hoverinfo='text',
            marker=Marker(
                opacity=0
            )
        )
        for edge in G.edges():
            edgeInfo=G.get_edge_data(edge[0],edge[1])
            if(typeinput in edgeInfo['label']):
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                edge_trace['x'] += [x0, x1, None]
                edge_trace['y'] += [y0, y1, None]
                middle_node_trace['x'].append((x0+x1)/2)
                middle_node_trace['y'].append((y0+y1)/2)
                middle_node_trace['text'].append(edgeInfo['label'])
        figureData.append(edge_trace)
        figureData.append(middle_node_trace)


    fig = Figure(data=Data(figureData),
                 layout=Layout(
                    title='<br>%s Network graph of %s'%(inputtype,tickerName),
                    titlefont=dict(size=16),
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20,l=5,r=5,t=40),
                    annotations=[ dict(
                        text="",
                        showarrow=False,
                        xref="paper", yref="paper",
                        x=0.005, y=-0.002 ) ],
                    xaxis=XAxis(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=YAxis(showgrid=False, zeroline=False, showticklabels=False)))

    div = plot(fig,auto_open=False,output_type='div')
    return div
# Create your views here.
def index(request):
    # stocks = Stock.objects.all()
    # for c in stocks:
    #     cp = {'q': c.name+',us', 'APPID': '6678584b2e111ae43c65b861fd657a0f'}
    #     info = requests.get('http://api.openweathermap.org/data/2.5/weather', params=cp).json()
    #     c.temp = info['main']['temp'] - 273.15
    #     c.save()
    # context = {'stocks': stocks}
    context = {}
    return render(request, 'stocks/index.html', context)

def info(request):
    form = StockForm(request.GET)
    form.is_valid()

    s = form.cleaned_data['input_string']
    ticker=None
    ticker=findTicker(s)
    if(ticker!=None):
        tickerNameBB=findCompanyNameFromBloomberg(ticker)
        authenticate("localhost:7474", "neo4j", "root")
        graph = Graph()
        graph.delete_all()
        tx=graph.begin()
        tx.run("CREATE (n:%s {name:{b}})"%"Company",b=tickerNameBB)
        tx.commit()

        executives,boardMembers=getCompanyKeyPersonnel(ticker)
        procs = []
         
        companyBoardInfo = Manager().list()
        proc = Process(target=getCompanyBoardInfo, args=(boardMembers,tickerNameBB,companyBoardInfo))
        procs.append(proc)
        proc.start()

        executivesInfo = Manager().list()
        proc = Process(target=getCompanyExecutivesInfo, args=(executives,tickerNameBB,executivesInfo))
        procs.append(proc)
        proc.start()

        competitorName = Manager().list()
        marketCap = Manager().list()
        proc = Process(target=getCompetitorInfo, args=(ticker,tickerNameBB,competitorName,marketCap))
        procs.append(proc)
        proc.start()

        stakeHoldersName = Manager().list()
        OverallPR = Value('d', 0)
        proc = Process(target=getStakeHolderInfo, args=(ticker,tickerNameBB,stakeHoldersName,OverallPR))
        procs.append(proc)
        proc.start()

        for proc in procs:
            proc.join()

        C,div3=produceGraph(tickerNameBB,companyBoardInfo,"BoardMember")

        D,div4=produceGraph(tickerNameBB,executivesInfo,"Executive")
        
        A,div1=produceGraph(tickerNameBB,competitorName,"Competitor")

        B,div2=produceGraph(tickerNameBB,stakeHoldersName,"StakeHolder")

        E=nx.compose_all([A,B,C,D])
        div5=printGraph(E,tickerNameBB,"Overall")

        boardcareerhistory=0
        boardboardmembership=0
        for board in companyBoardInfo:
            boardcareerhistory+=len(board[2])
            boardboardmembership+=len(board[3])
        avgboardcareerhistory=1.0/len(companyBoardInfo)*boardcareerhistory 
        avgboardboardmembership=1.0/len(companyBoardInfo)*boardboardmembership 
        executivecareerhistory=0
        executiveboardmembership=0
        for executive in executivesInfo:
            executivecareerhistory+=len(board[2])
            executiveboardmembership+=len(board[3])
        avgexecutivecareerhistory=1.0/len(executivesInfo)*executivecareerhistory 
        avgexecutiveboardmembership=1.0/len(executivesInfo)*executiveboardmembership

        summarized_text=""
        summarized_text+="There are %s nodes in total.\n"%str(graph.evaluate("MATCH (n) RETURN count(*)"))
        summarized_text+="The computed value (based on pagerank analysis of stakeholders) of the company is %0.2f millions.\n"%OverallPR.value
        summarized_text+="There are %d Competitors in the same industry.\n"%len(competitorName)
        summarized_text+="There are %d Stakeholders(with more than 1 percent shares).\n"%len(stakeHoldersName)
        summarized_text+="There are %d Boardmembers in the company:\n"%len(companyBoardInfo)
        summarized_text+="---Each Boardmembers has an average number of %d past career in other companies.\n"%avgboardcareerhistory
        summarized_text+="---Each Boardmembers has an average number of %d board membership experiences in other companies.\n"%avgboardboardmembership
        summarized_text+="There are %d Executives in the company:\n"%len(executivesInfo)
        summarized_text+="---Each Executives has an average number of %d past career in other companies.\n"%avgexecutivecareerhistory
        summarized_text+="---Each Executives has an average number of %d board membership experiences in other companies.\n"%avgexecutiveboardmembership

        labels = [x for x in competitorName]
        labels.insert(0,tickerNameBB)
        values = [x for x in marketCap]

        trace = graph_objs.Pie(labels=labels, values=values,textinfo='none')
        fig = Figure(data=Data([trace]))
        piechart=plot(fig,auto_open=False,output_type='div')

        context={'input_string':s,'piechart':piechart,'graph':div1,'graph2':div2,'graph3':div3,'graph4':div4,'graph5':div5,'summarized_text':summarized_text}
        # context={'input_string':s,'graph':div1}
    else:
        context={'input_string':s}
    return render(request, 'stocks/info.html', context)
