from datetime import datetime, timedelta
import uuid
import base64
from flask import request
import os
from  libs import logs, variables
from flask import make_response, request, jsonify
import json
import traceback
from sqlalchemy import or_, and_
import sqlalchemy


def initDatabase(db):
    from appsrc.model import User, OpeningHoursTemplate, RecurringSlotsTemplate, DailySchedule, Address, DistributionOwner, DistributionPoint, BookableSlot, BookedSlot
    if (len(db.session.query(User).all()) != 0):
        return
    logs.logger.info("Dropping DB")
    db.session.remove()
    db.session.commit()  
    db.drop_all()
    logs.logger.info("Creating a new version of the db")
    db.create_all()
    logs.logger.info("Adding Use")
    u = User(username=variables.DEFAULT_ADMIN_USERNAME,email=variables.DEFAULT_ADMIN_EMAIL,id=uuid.uuid4().__str__())
    u.set_password(variables.DEFAULT_ADMIN_PASSWORD)

    db.session.add(u)
    logs.logger.info("Adding address")
    # ADDRESS PART
    add_uid = uuid.uuid4().__str__()
    add = Address(id=add_uid, street='Rue Mertens', number="2", zipcode="92270", city="Bois Colombes", country="France")
    db.session.add(add)
    db.session.commit()
    logs.logger.info("Adding OHT")
    #openinghourstemplate
    sched = DailySchedule("09:00", "", "", "19:00")
    sched_str = sched.serialize.__str__()
    openHTemplateId = uuid.uuid4().__str__()
    openHTemplate = OpeningHoursTemplate(id=openHTemplateId, name="24/7", description="Open 24/7",mon=sched_str, tue=sched_str, wed=sched_str, thu=sched_str, fri=sched_str,
    sat=sched_str, sun=sched_str,)
    db.session.add(openHTemplate)
    db.session.commit()
    logs.logger.info("Adding RST")
    #recurringSlotsTemplateId
    recurringSlotsTemplateId = uuid.uuid4().__str__()
    recurringSlotsTemplate = RecurringSlotsTemplate(id=recurringSlotsTemplateId, name="Default template", description="default slot, 30 min slot length",
    slotLength=30, slotCapacity=10)
    db.session.add(recurringSlotsTemplate)
    db.session.commit()

    logs.logger.info("Adding DO")
    # DistributionOwner Part
    owner_id = uuid.uuid4().__str__()
    distO = DistributionOwner(id=owner_id, name="my name", description="my description", logoUrl="https://www.www.col", telephone="01203013123", email="koko@koko.com")
    distO.refAddressId = add.id
    db.session.add(distO)
    db.session.commit()
    logs.logger.info("Adding DP")
    #DistributionPoint Part
    distPart = uuid.uuid4().__str__()
    dP0 = DistributionPoint(id=distPart, name="my name", description="my description", logoUrl="https://www.www.col", telephone="01203013123", email="koko@koko.com",
        refAddressId = add.id,  refDistributionOwnerId=owner_id, maxCapacity=10, refOpeningHoursTemplateId=openHTemplateId, refRecurringSlotsTemplateId=recurringSlotsTemplateId)
    db.session.add(dP0)
    db.session.commit()
    logs.logger.info("Adding BS")
    # adds a bookable slot
    BS1Id = uuid.uuid4().__str__()
    now = datetime.now()
    BS = BookableSlot(id=BS1Id, dateStart=now - timedelta(minutes=1), dateEnd=now + timedelta(minutes=40), maxCapacity=2, refDistributionPointId=distPart, currentCapacity=2)
    db.session.add(BS)
    db.session.commit()

    BS11Id = uuid.uuid4().__str__()
    BS11 = BookableSlot(id=BS11Id, dateStart=now + timedelta(hours=1), dateEnd=now + timedelta(hours=2), maxCapacity=10, refDistributionPointId=distPart, currentCapacity=10)
    db.session.add(BS11)
    db.session.commit()


    BS2Id = uuid.uuid4().__str__()
    BS2 = BookableSlot(id=BS2Id, dateStart=now + timedelta(hours=23), dateEnd=now + timedelta(hours=25), maxCapacity=10, refDistributionPointId=distPart, currentCapacity=0)
    db.session.add(BS2)
    db.session.commit()


def checkReceivedContentAgainstForbiddenValues(received_request, curratedvalues):
    logs.logger.info("#### Checking values :{} and {}".format(received_request, curratedvalues))
    currated_fields = [d for d in curratedvalues]
    for entry in received_request:
        if (entry in currated_fields):
            logs.logger.info("a received param {} is in the currated values ".format(entry))
            if (received_request[entry] in curratedvalues[entry]['forbidenvalues']):
                raise Exception('{} is in forbidden values: {}'.format(entry, curratedvalues[entry]['forbidenvalues']))
            if ('allowedvalues' in curratedvalues[entry] and received_request[entry] not in curratedvalues[entry]['allowedvalues']):
                raise Exception('{} is not in allowed values : {}'.format(entry, curratedvalues[entry]['allowedvalues']))

def currateDictValue(receivedData, configurationFields):#, forbidden_values):
    try:
        logs.logger.debug("receivedData before currating: {}".format(receivedData))
    except Exception as e:
        raise Exception("Malformed json body")
    receivedFields = [d for d in receivedData]
    logs.logger.info("#### Checking values :{} and {}".format(receivedData, configurationFields))    
    logs.logger.info('#### received Fields {}'.format(receivedFields))

    for entry in configurationFields:
        logs.logger.info("Treating {}  -> {}  ".format(entry, configurationFields[entry]))
        if (entry not in receivedFields):
            if (configurationFields[entry]['isMandatory'] == True):
                raise Exception('{} is not availabe in received structure'.format(entry))
            else: # entry is not mandatory, adding it to the receivedData with a default value
                logs.logger.debug("Adding field {} with value {}".format(entry,  configurationFields[entry]['replaceValue']))
                receivedData[entry] = configurationFields[entry]['replaceValue']

        #logs.logger.info("entry.field -> {}".format(entry['field']))        
        #logs.logger.info("receiveddata[entry.fiele]-> {}".format(receivedData[entry['field']]))
        if (receivedData[entry] in configurationFields[entry]['forbidenvalues']):
            raise Exception('{} is in forbidden values: {}'.format(entry, configurationFields[entry]['forbidenvalues']))
        
        if ('allowedvalues' in configurationFields[entry] and receivedData[entry] not in configurationFields[entry]['allowedvalues']):
            raise Exception('{} is not in allowed values : {}'.format(configurationFields[entry]['field'], configurationFields[entry]['allowedvalues']))

    logs.logger.debug("receivedData AFTER currating: {}".format(receivedData))
    return receivedData

def validateUnicityOnUpdate(className, dict, id_):
    classNameStr = className.__jsonName__
    unicityCriteria = className.__unicityCriteria__
    unicityCriteriaOr = className.__unicityCriteriaOr__

    result = countObjectUnicity(className, dict)

    if (result == None):
        logs.logger.debug("Result is none, no unicity check on update for that kind of record -> {}".format(classNameStr))
        return result
    nbResults = len(result)
    logs.logger.debug("Nb Result = {} with unicity criteriaAnd {}  unicityCriteriaOr {} - id {} for object {}".format(nbResults, unicityCriteria,
            unicityCriteriaOr,  id_, classNameStr))

    # now checks id
    if (nbResults == 0):
        return result
    # ok print it
    for entry in result:
        logs.logger.debug(entry.serialize)

    # two cases : there is one record and it has the same id and  same name , so we are good to update it
    if (nbResults == 1 and  result[0].id == id_):   
        return result
    else:
        # same name and different id -> error
        # more than one .. -> erorr
        raise Exception('Unicity Error for object type {} - unicity criteriaAnd {} unicityCriteriaOr {} - id {}'.format(classNameStr, unicityCriteria,
                unicityCriteriaOr, id_))


def checksReferencesId(className, dict):
    #gets all fields within the class
    for entry in className.__checkReferenceFields__:
        if (entry in dict):
            logs.logger.info("Checking field {} Id {} exists in table {}".format(entry, dict[entry],className.__checkReferenceFields__[entry] ))
            try:
                tble = className.__checkReferenceFields__[entry]
                logs.logger.debug("About to call {} , primary context was {}".format(tble, className))
                tble.query.filter_by(id=dict[entry]).first_or_404()
                #resultFinal = tble.query.filter(and_(*request_filterAnd)).first_or_404()
            except Exception as e:
                raise   Exception('Error object {} {} is unknown '.format(entry,dict[entry]))


def countObjectUnicity(className, dict):
    request_filterAnd = []
    request_filterOr = []
    unicityCriteria = className.__unicityCriteria__
    unicityCriteriaOr = className.__unicityCriteriaOr__
    logs.logger.debug("unicityCritera  {} \n unicityCriteriaOr {} \n className {} \n dict {}  ".format(unicityCriteria, unicityCriteriaOr, className, dict))
    if (len(unicityCriteria) > 0):
        for entry in unicityCriteria:
            if (entry in dict):
                request_filterAnd.append(sqlalchemy.func.upper(className.__dict__[entry]) == (dict[entry]).upper())
        #resultAnd = className.query.filter(and_(*request_filter))

    if (len(unicityCriteriaOr) > 0):
        for entry in unicityCriteriaOr:
            if (entry in dict):
                request_filterOr.append(sqlalchemy.func.upper(className.__dict__[entry]) == (dict[entry]).upper())
        #resultOr = className.query.filter(or_(*request_filter))
    
    if (len(request_filterAnd) == 0 and len(request_filterOr) == 0): #this means the field being update is not in the list of monitored fields
        logs.logger.info("--> 1 ")
        return None

    if (len(unicityCriteria) == 0 and len(unicityCriteriaOr) == 0):
        logs.logger.info("--> 2")
        resultFinal = None
    elif (len(unicityCriteria) > 0 and len(unicityCriteriaOr) > 0):
        resultFinal = className.query.filter(or_(*request_filterOr), and_(*request_filterAnd)).all()
        logs.logger.info("--> 3")
    elif (len(unicityCriteria) == 0 and len(unicityCriteriaOr) > 0):
        resultFinal = className.query.filter(or_(*request_filterOr)).all()
        logs.logger.info("--> 4")
    elif (len(unicityCriteria) > 0 and len(unicityCriteriaOr) == 0):        
        resultFinal = className.query.filter(and_(*request_filterAnd)).all()
        logs.logger.info("--> 5")

    return resultFinal

def checkObjectUnicity(className, dict ):
    result = countObjectUnicity(className, dict)
    classNameStr = className.__jsonName__
    unicityCriteria = className.__unicityCriteria__
    unicityCriteriaOr = className.__unicityCriteriaOr__
    if (result != None):
        for entry in result:
            logs.logger.debug(entry)
            #logs.logger.debug(entry.serialize)
    if (result != None):
        if (len (result) > 0): # and result.count != 0 ):
          raise Exception('Unicity Error for object type {} - unicity criteriaAND {} , unicityCriteriaOR {} '.format(classNameStr, unicityCriteria, unicityCriteriaOr))

    
def returnResponse(data, code):
    resp = make_response(data, code )
    return resp, code

def getArgs(default, request, argName):
    if ((request.args.get(argName) != None) & (request.args.get(argName) !='')):
        return request.args.get(argName)
    return default

def getForm(default, request, argName):
    if ((request.form.get(argName) != None) & (request.form.get(argName) !='')):
        return request.form.get(argName)
    return default

def get_debug_all(request):
    str_debug = '* url: {}\n* method:{}\n'.format(request.url, request.method)
    
    str_debug += '* Args:\n'
    for entry in request.args:
        str_debug = str_debug + '\t* {} = {}\n'.format(entry, request.args[entry])
    str_debug += '* Headers:\n'
    for entry in request.headers:
        str_debug = str_debug + '\t* {} = {}\n'.format(entry[0], entry[1])
    str_debug += '* Form:\n'
    for entry in request.form:
        str_debug = str_debug + '\t* {} = {}\n'.format(entry, request.form[entry])        
    str_debug += '* Files:\n'        
    for entry in request.files :
        str_debug = str_debug +  '\t* {} = {}\n'.format(entry, request.files[entry])       
    str_debug += '* JSON:\n'                
    if (request.json!= None):
        str_debug = str_debug +  '\t* Json = {}\n'.format(request.json)       
    return str_debug    

def checkAuthorization(request):
    if ("Authorization" not in request.headers):
        logs.logger.error("Authorization code is not in headers")
        return  False, None
    else:
        authorizationCode = request.headers['Authorization']
        #base decode
        authorizationCodeB64 = authorizationCode.split(" ")[1]
        logs.logger.info("Authorization Code in B64={}".format(authorizationCodeB64))
        decoded = base64.b64decode(authorizationCodeB64)
        logs.logger.info("Authorization Code decoded={}".format(decoded))

        return  True, decoded       

def getDayFromStr(date):
    today = datetime.strptime((datetime.now()).strftime(variables.DATE_PATTERN), variables.DATE_PATTERN)
    return today

def getCurrentDay():
    today = datetime.strptime((datetime.now()).strftime(variables.DATE_PATTERN), variables.DATE_PATTERN)
    return today

def getTomorrowDT():
    tomorrow = datetime.strptime((datetime.now() + timedelta(days=1)).strftime(variables.DATE_PATTERN), variables.DATE_PATTERN)
    return tomorrow

def getDateFromStr(str, pattern):
    return datetime.strptime(str, pattern)

def dateToStr(date, pattern):
    return date.strftime(pattern)