#!/usr/bin/env python3
"""One-station historic waveform forensic evidence; no mechanical-truth adoption.
Official GeoCSV provides actual decoded samples. miniSEED fixed headers and
STEIM2 integration endpoints are independently audited; no claim to independently
unpack every STEIM2 interior sample. Original44pkg environment only.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,io,json,struct,urllib.parse,urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];I=R/'inputs/waveform';O=R/'results/waveform';C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/waveform');UTC=dt.timezone.utc
QSTART=dt.datetime(2026,8,26,2,20,tzinfo=UTC);QEND=dt.datetime(2026,8,26,3,10,tzinfo=UTC)
BASE='https://service.earthscope.org/';P={'net':'NK','sta':'KKN','loc':'--','cha':'BHZ','start':'2026-08-26T02:20:00','end':'2026-08-26T03:10:00','nodata':'404'}
URLS={'NK_KKN_BHZ_0220_0310.mseed':BASE+'fdsnws/dataselect/1/query?'+urllib.parse.urlencode(P),'NK_KKN_BHZ_0220_0310.geocsv':BASE+'fdsnws/dataselect/1/query?'+urllib.parse.urlencode(dict(P,format='geocsv.inline')),'NK_KKN_BHZ_response.xml':BASE+'fdsnws/station/1/query?'+urllib.parse.urlencode(dict(P,level='response',format='xml')),'mustang_20260826.txt':BASE+'mustang/measurements/1/query?metric=percent_availability,max_gap,num_gaps&target=NK.KKN.*.BH?.*,IO.EVN.*.BH?.*,IO.EVN.*.HH?.*,IC.LSA.*.BHZ.*&start=2026-08-26&end=2026-08-27&format=text','dataselect_docs.html':BASE+'fdsnws/dataselect/1/','station_docs.html':BASE+'fdsnws/station/1/'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def stamp(x):return x.isoformat().replace('+00:00','Z')
def fetch(n,u):
 p=C/n
 if p.exists():return
 start=stamp(dt.datetime.now(UTC))
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Q3ForensicWaveform/1.0'}),timeout=90);b=r.read();p.write_bytes(b);j={'canonical_url_or_product_id':u,'requested_at_utc':start,'retrieved_at_utc':stamp(dt.datetime.now(UTC)),'status':r.status,'content_type':r.headers.get('Content-Type'),'bytes':len(b),'sha256':sha(p),'cache_path':str(p),'headers':{k:v for k,v in r.headers.items() if k.lower() not in ('set-cookie','cookie')},'available_time_or_unknown':None}
 except Exception as e:j={'canonical_url_or_product_id':u,'requested_at_utc':start,'status':'failed','error':str(e)}
 dump(C/(n+'.request.json'),j)
def parse_geocsv():
 s=(C/'NK_KKN_BHZ_0220_0310.geocsv').read_text();lines=s.splitlines();meta={}
 for line in lines:
  if line.startswith('#') and ': ' in line:
   k,v=line[1:].strip().split(': ',1);meta[k]=v
 data=pd.read_csv(io.StringIO('\n'.join(x for x in lines if not x.startswith('#'))))
 times=pd.to_datetime(data.iloc[:,0],utc=True);ns=times.astype('int64').to_numpy();y=pd.to_numeric(data.iloc[:,1]).to_numpy(np.int64);return meta,ns,y

def rate(f,m):return (f if f>0 else -1/f)*(m if m>0 else -1/m)
def parse_mseed(ns,y):
 b=(C/'NK_KKN_BHZ_0220_0310.mseed').read_bytes();out=[];pos=0;checks=[]
 while pos<len(b):
  h=b[pos:pos+48];year,doy,hour,minute,sec,res,fract,n,f,m,af,iof,dqf,nb,correction,dataoff,boff=struct.unpack('>HHBBBBHHhhBBBBiHH',h[20:48]);assert 1900<year<2100 and 0<doy<367
  start=dt.datetime(year,1,1,tzinfo=UTC)+dt.timedelta(days=doy-1,hours=hour,minutes=minute,seconds=sec,microseconds=fract*100)
  # SEED activity bit1 means fixed-header time correction already applied.
  if correction and not (af&2):start+=dt.timedelta(microseconds=correction*100)
  enc=wordorder=reclen=None;timing=us=None;seen=set();offset=boff
  while offset and offset not in seen:
   seen.add(offset);typ,nxt=struct.unpack('>HH',b[pos+offset:pos+offset+4]);payload=b[pos+offset+4:pos+offset+8]
   if typ==1000:enc,wordorder,exp,_=struct.unpack('BBBB',payload);reclen=2**exp
   elif typ==1001:timing,us,_,_=struct.unpack('BbBB',payload);start+=dt.timedelta(microseconds=us)
   offset=nxt
  assert reclen and enc==11,'only observed STEIM2 records supported for integration endpoint audit'
  fs=rate(f,m);end=start+dt.timedelta(seconds=(n-1)/fs);endian='>' if wordorder==1 else '<';x0,xn=struct.unpack(endian+'ii',b[pos+dataoff+4:pos+dataoff+12]);startns=int(pd.Timestamp(start).value);endns=int(pd.Timestamp(end).value)
  ii=np.searchsorted(ns,startns);jj=np.searchsorted(ns,endns);match=ii<len(ns) and jj<len(ns) and ns[ii]==startns and ns[jj]==endns and y[ii]==x0 and y[jj]==xn
  checks.append(bool(match));out.append({'record_index':len(out),'byte_offset':pos,'record_length':reclen,'sequence':h[:6].decode(),'quality_indicator':chr(h[6]),'network':h[18:20].decode().strip(),'station':h[8:13].decode().strip(),'location':h[13:15].decode().strip(),'channel':h[15:18].decode().strip(),'start_utc':stamp(start),'end_utc':stamp(end),'sample_count':n,'sample_rate_hz':fs,'encoding':enc,'word_order':wordorder,'activity_flags':af,'io_clock_flags':iof,'data_quality_flags':dqf,'time_correction_1e4_seconds':correction,'timing_quality_reported':timing,'microsecond_correction':us,'steim2_x0':x0,'steim2_xn':xn,'geocsv_endpoint_match':bool(match)})
  pos+=reclen
 assert pos==len(b)
 return pd.DataFrame(out),checks

def inventory():
 root=ET.parse(C/'NK_KKN_BHZ_response.xml').getroot();n={'s':'http://www.fdsn.org/xml/station/1'};net=root.find('s:Network',n);st=net.find('s:Station',n);ch=st.find('s:Channel',n)
 def value(path):
  x=ch.find('s:'+path.replace('/','/s:'),n);return x.text.strip() if x is not None and x.text else None
 return {'station_id':'NK.KKN..BHZ','channel_attributes':ch.attrib,'station_attributes':st.attrib,'network_attributes':net.attrib,'latitude':float(value('Latitude')),'longitude':float(value('Longitude')),'elevation_m':float(value('Elevation')),'depth_m':float(value('Depth')),'azimuth_degrees':float(value('Azimuth')),'dip_degrees':float(value('Dip')),'sample_rate_hz':float(value('SampleRate')),'sensor':value('Sensor/Description'),'instrument_sensitivity':float(value('Response/InstrumentSensitivity/Value')),'sensitivity_frequency_hz':float(value('Response/InstrumentSensitivity/Frequency')),'input_units':value('Response/InstrumentSensitivity/InputUnits/Name'),'output_units':value('Response/InstrumentSensitivity/OutputUnits/Name'),'response_stage_count':len(ch.findall('s:Response/s:Stage',n)),'response_removed':False,'signal_units_used':'rawcounts; no sensitivity-only scaling misrepresented as full response correction','absolute_UTC_accuracy_seconds':None,'absolute_UTC_accuracy_reason':'archive stamps and reported timing quality; no independent clock calibration in this packet','distance_to_advisor_candidate_source_km':58.38,'distance_provenance':'trusted main-advisor channel/source check, not recomputed geometry; not a verified radiation origin'}

def mustang():
 rows=[];section=None
 for line in (C/'mustang_20260826.txt').read_text().splitlines():
  if line.startswith('"') and ','not in line:section=line.strip('"');continue
  if line.startswith('"value"') or not line.strip():continue
  values=next(csv.reader([line]))
  if len(values)==5 and values[1]=='NK.KKN..BHZ.M':rows.append(dict(metric=section,value=values[0],target=values[1],start=values[2],end=values[3],lddate=values[4]))
 return rows

def features(ns,y,fs):
 # Only complete 1-second bins. Inclusive last endpoint remains in the raw source/QC.
 N=len(y)//int(fs)*int(fs);raw=y[:N].astype(float);starts=ns[:N:int(fs)];baseline=(ns>=pd.Timestamp('2026-08-26T02:22:00Z').value)&(ns<pd.Timestamp('2026-08-26T02:28:00Z').value);center=float(np.median(y[baseline]));x=raw-center
 d=pd.DataFrame({'bin_start_utc':pd.to_datetime(starts,utc=True).astype(str),'feature_support_end_utc':pd.to_datetime(starts+int(1e9),utc=True).astype(str),'raw_min_counts':raw.reshape(-1,int(fs)).min(1),'raw_max_counts':raw.reshape(-1,int(fs)).max(1),'raw_rms_counts':np.sqrt(np.mean(x.reshape(-1,int(fs))**2,axis=1))})
 bands={'low_0.02_0.2Hz':(.02,.2),'mid_0.2_1Hz':(.2,1),'high_1_10Hz':(1,10)};noise=[];events=[]
 mask=(starts>=pd.Timestamp('2026-08-26T02:22:00Z').value)&(starts<pd.Timestamp('2026-08-26T02:28:00Z').value);scan=starts>=pd.Timestamp('2026-08-26T02:28:00Z').value
 for name,(low,high) in bands.items():
  filtered=signal.sosfilt(signal.butter(4,[low,high],btype='bandpass',fs=fs,output='sos'),x);rms=np.sqrt(np.mean(filtered.reshape(-1,int(fs))**2,axis=1));logs=np.log(np.maximum(rms,1e-12));med=float(np.median(logs[mask]));mad=float(1.4826*np.median(abs(logs[mask]-med)));assert mad>0;z=(logs-med)/mad;d[name+'_rms_counts']=rms;d[name+'_robust_log_z']=z;noise.append({'band':name,'baseline_start_utc':'2026-08-26T02:22:00Z','baseline_end_exclusive_utc':'2026-08-26T02:28:00Z','baseline_rms_median_counts':float(np.median(rms[mask])),'baseline_log_rms_median':med,'baseline_log_rms_scaled_MAD':mad,'max_rms_counts':float(rms.max()),'max_rms_support_end_utc':d.feature_support_end_utc.iloc[int(rms.argmax())],'max_robust_log_z':float(z.max()),'causal_filter':True,'filter_group_delay_seconds':None,'units':'counts; relative band-limited amplitude, not calibrated physicalenergy'})
  for thresh in (4,6,8):
   hit=(z>=thresh)&scan;edges=np.diff(np.r_[False,hit,False].astype(int));beg=np.where(edges==1)[0];end=np.where(edges==-1)[0]
   for i,j in zip(beg,end):
    if j-i<5:continue
    peak=i+int(np.argmax(z[i:j]));events.append({'station_id':'NK.KKN..BHZ','band':name,'threshold_robust_log_z':thresh,'episode_start_bin_utc':d.bin_start_utc.iloc[i],'first_exceedance_support_end_utc':d.feature_support_end_utc.iloc[i],'five_bin_confirmation_support_end_utc':d.feature_support_end_utc.iloc[i+4],'episode_end_exclusive_utc':d.feature_support_end_utc.iloc[j-1],'duration_seconds':int(j-i),'peak_feature_support_end_utc':d.feature_support_end_utc.iloc[peak],'peak_robust_log_z':float(z[peak]),'peak_rms_counts':float(rms[peak]),'data_role':'retrospective_station_signal_candidate','physical_phase':'station_elevated_band_energy_candidate','source_phase_linkage':'unknown','accepted_first_mechanical_initiation_truth':False,'filter_and_path_delay_unknown':True})
 return d,pd.DataFrame(events),noise,center

def plots(d,episodes,ns,y,fs):
 times=pd.to_datetime(d.feature_support_end_utc,utc=True);t=(times-pd.Timestamp(QSTART)).dt.total_seconds().to_numpy()/60;fig,axs=plt.subplots(4,1,figsize=(11,9),sharex=True,constrained_layout=True)
 axs[0].fill_between(t,d.raw_min_counts,d.raw_max_counts,color='#4b6178',alpha=.7);axs[0].set_ylabel('Rawcounts\n1s min/max')
 for ax,name,c in zip(axs[1:],['low_0.02_0.2Hz','mid_0.2_1Hz','high_1_10Hz'],['#28769d','#9e7031','#a24c42']):
  ax.plot(t,d[name+'_rms_counts'],color=c,lw=.8);ax.set_yscale('log');ax.set_ylabel(name.replace('_',' ')+'\nRMS counts');ax.axvspan(2,8,color='#b7bfca',alpha=.2)
 for ax in axs:
  ax.axvline(10,color='#777',ls=':',lw=1);ax.axvline(31+50/60,color='#6d3e8c',ls='--',lw=1);ax.axvline(32+10/60,color='#282828',ls='--',lw=1);ax.spines[['top','right']].set_visible(False)
 axs[-1].set_xlabel('Minutes since 2026-08-26 02:20:00 UTC; causal 1s RMS data support ends at bin end; archive latency unknown');axs[0].set_title('NK.KKN..BHZ actual waveform, 50Hz / 150001 samples\nReference lines only: 02:30 problem, 02:51:50 reconstruction, 02:52:10 USGS proxy; no source-truth adoption',fontsize=11);fig.savefig(O/'waveform_bands.png',dpi=160);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,4.5),constrained_layout=True);regions=[('baseline02:22–02:28',120,480,'#66818f'),('reference02:29–02:33',540,780,'#a67b3e'),('catalogue02:50–02:56',1800,2160,'#9e4c4a')];yy=y.astype(float);tt=(ns-ns[0])/1e9
 for name,start,end,c in regions:
  seg=yy[(tt>=start)&(tt<end)];f,p=signal.welch(seg,fs=fs,nperseg=min(2048,len(seg)),detrend='linear');ax.loglog(f[1:],p[1:],label=name,color=c)
 ax.set_xlim(.02,15);ax.set_xlabel('Frequency (Hz)');ax.set_ylabel('PSD counts²/Hz');ax.set_title('Fixed reference-window spectra; instrument response not removed');ax.legend(frameon=False);ax.spines[['top','right']].set_visible(False);fig.savefig(O/'waveform_spectra.png',dpi=160);plt.close(fig)

def phase_review(episodes):
 rows=[]
 for band in ('low_0.02_0.2Hz','mid_0.2_1Hz','high_1_10Hz'):
  for threshold in (4,6,8):
   selected=episodes[(episodes.band==band)&(episodes.threshold_robust_log_z==threshold)].sort_values('episode_start_bin_utc')
   row={'band':band,'threshold_robust_log_z':threshold,'candidate_episode_count':len(selected),'first_episode_start_bin_utc':None,'first_confirmation_support_end_utc':None,'status':'no_persistent_candidate' if selected.empty else 'station_candidate_only','accepted_mechanical_truth':False}
   if len(selected):row.update(first_episode_start_bin_utc=selected.iloc[0].episode_start_bin_utc,first_confirmation_support_end_utc=selected.iloc[0].five_bin_confirmation_support_end_utc)
   rows.append(row)
 pd.DataFrame(rows).to_csv(O/'threshold_summary.csv',index=False)
 dump(O/'phase_review.json',{'station_id':'NK.KKN..BHZ','data_role':'retrospective_station_signal_phase_proxy','candidate_episode_count':len(episodes),'independent_disaster_event_count_from_episodes':None,'source_phase_linkage':'unknown','accepted_local_first_mechanical_truth_count':0,'accepted_source_initiation_UTC':None,'historical_first_available_time':None,'clock_error_seconds':None,'propagation_travel_time_seconds':None,'causal_filter_group_delay_seconds':None,'minimum_persistence_bins':5,'feature_time_semantics':'1s sample_support_end; no historicalavailability claim','baseline_selection':'fixed before viewing, not independently verified quiet','reference_line_times_are_ground_truth':False,'all_threshold_combinations_retained':True,'full_STEIM2_interior_independently_decoded':False})

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--collect',action='store_true');args=ap.parse_args();assert (I/'protocol.json').exists();O.mkdir(parents=True,exist_ok=True);C.mkdir(parents=True,exist_ok=True)
 if args.collect:
  for n,u in URLS.items():fetch(n,u)
 meta,ns,y=parse_geocsv();fs=float(meta['sample_rate_hz']);records,endpointchecks=parse_mseed(ns,y);inv=inventory();daily=mustang();records.to_csv(O/'miniseed_records.csv',index=False)
 gaps=np.where(np.diff(ns)!=int(round(1e9/fs)))[0];gaprows=[{'previous_sample_utc':str(pd.to_datetime(ns[i],utc=True)),'next_sample_utc':str(pd.to_datetime(ns[i+1],utc=True)),'step_seconds':float((ns[i+1]-ns[i])/1e9),'expected_step_seconds':1/fs} for i in gaps];pd.DataFrame(gaprows,columns=['previous_sample_utc','next_sample_utc','step_seconds','expected_step_seconds']).to_csv(O/'sample_clock_anomalies.csv',index=False)
 d,episodes,noise,center=features(ns,y,fs);d.to_csv(O/'features_1s.csv',index=False,float_format='%.12g');episodes.to_csv(O/'candidate_episodes.csv',index=False,float_format='%.12g');dump(O/'noise_and_peaks.json',{'baseline_center_counts':center,'bands':noise});dump(O/'station_inventory.json',inv);dump(O/'mustang_summary.json',{'rows_for_KKN_BHZ_M':daily,'note':'dailyMUSTANG quality.M metric target vs submitted miniSEED D indicator kept distinct; current data actualsample clock audited separately','parent_retrieval_sha256':'0ceba70914831549d62742de5b7fa158701b157aa26e93bc3fae04f622d10bdb','this_retrieval_sha256':sha(C/'mustang_20260826.txt'),'identity_to_parent_bytes':sha(C/'mustang_20260826.txt')=='0ceba70914831549d62742de5b7fa158701b157aa26e93bc3fae04f622d10bdb','difference_cause':'not independently compared; do not assert same version solely by equal bytes'})
 checks=[{'test':'geocsv_header_samplecount','passed':len(y)==int(meta['sample_count'])},{'test':'requested_exact_UTC_endpoints','passed':int(ns[0])==int(pd.Timestamp(QSTART).value) and int(ns[-1])==int(pd.Timestamp(QEND).value)},{'test':'uniform50Hz_no_sample_gaps_overlap','passed':fs==50 and len(gaps)==0},{'test':'station_response_sample_rate_matches','passed':inv['sample_rate_hz']==fs},{'test':'miniseed_record_sample_counts_match','passed':int(records.sample_count.sum())==len(y)},{'test':'all_STEIM2_X0_Xn_endpoints_match_official_GeoCSV','passed':all(endpointchecks)},{'test':'one_requested_NSLC_only','passed':set(records.network)=={'NK'} and set(records.station)=={'KKN'} and set(records.channel)=={'BHZ'} and set(records.location)=={''}},{'test':'one_second_complete_bins_only','passed':len(d)==3000},{'test':'all_raw_and_features_finite','passed':bool(np.isfinite(y).all() and np.isfinite(d.select_dtypes(include=[np.number]).to_numpy()).all())},{'test':'no_mechanical_truth_auto_adopted','passed':not episodes.accepted_first_mechanical_initiation_truth.any() if len(episodes) else True}]
 dump(O/'validation.json',{'passed':all(x['passed'] for x in checks),'checks':checks,'raw_sample_count':len(y),'sample_rate_hz':fs,'raw_start_utc':str(pd.to_datetime(ns[0],utc=True)),'raw_end_utc':str(pd.to_datetime(ns[-1],utc=True)),'actual_sample_gaps_or_overlap':len(gaps),'miniseed_record_count':len(records),'miniseed_payload_decode_scope':'fixed header+1000/1001+STEIM2 integration X0/Xn; interior samples supplied by officialGeoCSV, not independently unpacked','quality_indicators':sorted(set(records.quality_indicator)),'timing_quality_reported_values':sorted(set(int(x) for x in records.timing_quality_reported.dropna())),'data_quality_flags_values':sorted(set(int(x) for x in records.data_quality_flags)),'ADC_raw_min':int(y.min()),'ADC_raw_max':int(y.max()),'independent_clock_accuracy_seconds':None,'event_label_added_count':0,'mechanical_truth_timestamp_accepted':False,'protocol_sha256':sha(I/'protocol.json'),'waveform_sha256':sha(C/'NK_KKN_BHZ_0220_0310.mseed'),'GeoCSV_sha256':sha(C/'NK_KKN_BHZ_0220_0310.geocsv'),'dependencies':{'numpy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__},'original_environment_changed':False,'feature_support_end_not_available_time':True,'sensor_historical_first_available_time':None,'baseline_parameter_estimation_complete_support_end':'2026-08-26T02:28:00Z','candidate_evaluation_starts_after_baseline':True})
 sources=[]
 for n,u in URLS.items():
  p=C/n;log=C/(n+'.request.json');j=json.loads(log.read_text()) if log.exists() else {};sources.append({'canonical_url_or_product_id':u,'product_version':'NSLC+fixed20260826window; current archive representation; FDSNserviceversion1 API','retrieved_at_utc':j.get('retrieved_at_utc'),'actual_read_scope':{'NK_KKN_BHZ_0220_0310.mseed':'allfixedheaders/blockettes plus eachSTEIM2X0Xn; noindependentfullSTEIM2decode','NK_KKN_BHZ_0220_0310.geocsv':'all150001rawcount/time samplepairs and headers','NK_KKN_BHZ_response.xml':'KKN/BHZ sensor/channel/response sensitivity and stagecount; no response deconvolution','mustang_20260826.txt':'KKN.BHZ.M rows for three dailymetrics; other targets retrievedin same explicit parentquery not interpreted','dataselect_docs.html':'actualformat/blanklocation/quality retirement/GeoCSV and timequery instructions','station_docs.html':'channel epoch and response metadata instructions'}.get(n),'bytes':p.stat().st_size if p.exists() else None,'sha256':sha(p) if p.exists() else None,'cache_path':str(p),'request_log':str(log),'data_role':'retrospective_waveform_phase_evidence' if n.endswith(('.mseed','.geocsv','.xml')) else 'availability_or_service_documentation','available_time_or_unknown':None,'status':j.get('status')})
 dump(R/'results/waveform_sources.json',{'sources':sources,'historical_realtime_availability':'unknown; current successfulretrieval andMUSTANGposteventmetriclddate not firstpublicavailability','source_truth':'not_adopted','rawdata_station':'NK.KKN..BHZ','no_new_dependencies_installed':True});plots(d,episodes,ns,y,fs);phase_review(episodes)
 print(json.dumps({'passed':all(x['passed'] for x in checks),'samples':len(y),'records':len(records),'candidate_episodes':len(episodes),'accepted_mechanical_truth':False}));print(pd.DataFrame(noise).to_string(index=False));print(episodes.groupby(['band','threshold_robust_log_z']).agg(episodes=('station_id','size'),first_bin=('episode_start_bin_utc','min')).to_string())
if __name__=='__main__':main()
