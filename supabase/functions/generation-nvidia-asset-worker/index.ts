import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SERVICE="asset-external-provider-smoke-control";
const VERSION="1.1.1";
const REPOSITORY="ersinbulduk6868/iss-ror-smoke";
const REPOSITORY_ID="1362644102";
const REF="refs/heads/main";
const OIDC_ISSUER="https://token.actions.githubusercontent.com";
const OIDC_JWKS="https://token.actions.githubusercontent.com/.well-known/jwks";
const OIDC_AUDIENCE="iss-asset-provider-smoke";
const ALLOWED_WORKFLOW_REFS=new Set([
  `${REPOSITORY}/.github/workflows/asset-external-provider-smoke.yml@${REF}`,
  `${REPOSITORY}/.github/workflows/blender-real-model-collision.yml@${REF}`,
]);
const EXACT_SOURCE_ALLOWLIST:Record<string,{label:string,expectedSourceSha256:string|null}>={
  "b06a715d23a7450babac383b8bb7fb0a":{
    label:"Bulldozer Candidate 1",
    expectedSourceSha256:"2c0be359bbc6c99118751e7caa4b71a205961914e78d2e58c5dd7afc0f498468",
  },
  "820a13c4831c41959ce75e6c2014e882":{
    label:"Generic Sport Coupé Car",
    expectedSourceSha256:null,
  },
};
let jwksCache:{expires:number,keys:any[]}|null=null;

Deno.serve(async(req:Request)=>{
  if(req.method!=="POST")return respond({success:false,error:"method not allowed"},405);
  try{
    const claims=await authenticateGitHub(req);
    const body=await req.json().catch(()=>({}));
    const mode=String(body?.mode??"").trim();
    const sketchfabToken=(Deno.env.get("SKETCHFAB_OAUTH_ACCESS_TOKEN")??Deno.env.get("SKETCHFAB_ACCESS_TOKEN")??Deno.env.get("SKETCHFAB_TOKEN")??"").trim();
    if(mode==="status"){
      return respond({success:true,service:SERVICE,version:VERSION,status:"READY",repository:REPOSITORY,workflowRef:claims.workflow_ref,runId:claims.run_id,sketchfabCredentialPresent:Boolean(sketchfabToken),exactSourceDownloadEnabled:true});
    }
    if(mode==="signed_source_download"){
      if(!sketchfabToken)return respond({success:false,service:SERVICE,version:VERSION,status:"SOURCE_DOWNLOAD_BLOCKED",error:"SKETCHFAB_CREDENTIAL_MISSING"},503);
      const uid=String(body?.uid??"").trim();
      const allowed=EXACT_SOURCE_ALLOWLIST[uid];
      if(!allowed)return respond({success:false,service:SERVICE,version:VERSION,status:"SOURCE_DOWNLOAD_REJECTED",error:"SOURCE_UID_NOT_ALLOWLISTED"},403);
      const detail=await sketchfabJson(`https://api.sketchfab.com/v3/models/${encodeURIComponent(uid)}`,sketchfabToken);
      if(detail?.isDownloadable!==true)return respond({success:false,service:SERVICE,version:VERSION,status:"SOURCE_DOWNLOAD_BLOCKED",error:"SOURCE_NOT_DOWNLOADABLE"},409);
      const info=await sketchfabJson(`https://api.sketchfab.com/v3/models/${encodeURIComponent(uid)}/download`,sketchfabToken);
      const candidate=(info?.glb&&typeof info.glb==="object"?{kind:"glb",...info.glb}:info?.gltf&&typeof info.gltf==="object"?{kind:"gltf",...info.gltf}:null);
      if(!candidate||typeof candidate.url!=="string"||!candidate.url)return respond({success:false,service:SERVICE,version:VERSION,status:"SOURCE_DOWNLOAD_BLOCKED",error:"NO_GLB_OR_GLTF_DOWNLOAD_ARTIFACT"},409);
      let parsed:URL;try{parsed=new URL(candidate.url);}catch{return respond({success:false,error:"SIGNED_URL_INVALID"},502);}
      if(parsed.protocol!=="https:")return respond({success:false,error:"SIGNED_URL_NON_HTTPS"},502);
      return respond({success:true,service:SERVICE,version:VERSION,status:"SIGNED_SOURCE_READY",source:{provider:"sketchfab",uid,label:allowed.label,expectedSourceSha256:allowed.expectedSourceSha256,artifactKind:candidate.kind,declaredBytes:Number(candidate.size??0)||null,signedUrl:candidate.url,expiresShortly:true}});
    }
    if(mode!=="run_smoke")return respond({success:false,error:"unsupported mode"},400);
    const result=await invokeAssetService();
    const actor=result?.masterAssets?.find((x:any)=>x?.entityId==="sports_car_fleet")??result?.masterAssets?.[0]??null;
    const candidates=Array.isArray(actor?.providerCandidates)?actor.providerCandidates:[];
    const valid=candidates.filter((c:any)=>c?.provider==="sketchfab"&&["CC0","CC_BY_4_0"].includes(String(c?.licenseCode??""))&&/^https:\/\//.test(String(c?.viewerUrl??"")));
    const pass=result?.service==="asset-service"&&result?.status==="ASSET_SOURCE_REVIEW_REQUIRED"&&result?.executionCompleted===false&&result?.assetLibrary?.productionAssetResolutionComplete===false&&result?.diagnostics?.externalProviderExecutionConnected===true&&actor?.category==="sports_car"&&actor?.resolutionStatus==="EXTERNAL_PROVIDER_CANDIDATES_FOUND"&&candidates.length>0&&valid.length===candidates.length;
    if(!pass)return respond({success:false,service:SERVICE,version:VERSION,status:"SMOKE_FAILED",assetServiceResult:result},502);
    return respond({success:true,service:SERVICE,version:VERSION,status:"SMOKE_PASS",marker:"ASSET_EXTERNAL_PROVIDER_HANDOFF=PASS",candidateCount:candidates.length,candidates:candidates.slice(0,5),assetServiceResult:{service:result.service,version:result.version,status:result.status,productionAssetResolutionComplete:result.assetLibrary?.productionAssetResolutionComplete,externalProvider:result.diagnostics?.externalProvider,category:actor?.category}});
  }catch(e){return respond({success:false,service:SERVICE,version:VERSION,status:"CONTROL_ERROR",error:e instanceof Error?e.message:String(e)},500);}
});

async function sketchfabJson(url:string,token:string){
  const u=new URL(url);if(u.protocol!=="https:"||u.hostname!=="api.sketchfab.com")throw new Error("UNEXPECTED_SKETCHFAB_API_URL");
  const r=await fetch(u.toString(),{headers:{Authorization:`Token ${token}`,Accept:"application/json","User-Agent":"Infinite-Shorts-Studio-Exact-Source-Relay/1.0"},signal:AbortSignal.timeout(30000)});
  const text=await r.text();if(!r.ok)throw new Error(`SKETCHFAB_HTTP_${r.status}:${text.slice(0,600)}`);
  const data=JSON.parse(text);if(!data||typeof data!=="object"||Array.isArray(data))throw new Error("SKETCHFAB_RESPONSE_INVALID");return data;
}

async function invokeAssetService(){
  const base=(Deno.env.get("SUPABASE_URL")??"").trim().replace(/\/$/,"");
  const key=(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")??"").trim();
  if(!base||!key)throw new Error("Supabase service environment missing");
  const payload={idea:"50 generic sports cars versus one giant bulldozer",language:"English",duration:15,aspectRatio:"9:16",classification:{requiresBrandReview:false},visualBible:{entityLocks:[{id:"sports_car_fleet",role:"sports car fleet",type:"sports car",appearance:"generic modern sports coupe, realistic road car, no specific brand",scale:"real world passenger sports car",materials:"painted metal, glass, rubber",distinguishingFeatures:["low sports coupe silhouette","four road wheels"],persistentStateRule:"preserve exact vehicle identity and damage state"}]},scenes:[{sceneNumber:1,visualPrompt:"Generic sports cars line up on an industrial proving ground.",action:"The sports cars accelerate toward the arena."},{sceneNumber:2,visualPrompt:"Generic sports cars maneuver around a heavy machine.",action:"The cars execute a coordinated approach."},{sceneNumber:3,visualPrompt:"Generic sports cars remain in the same continuous arena.",action:"The confrontation escalates without resetting the world."}]};
  const r=await fetch(`${base}/functions/v1/asset-service`,{method:"POST",headers:{"Content-Type":"application/json",apikey:key,Authorization:`Bearer ${key}`,"x-workflow-id":`asset-provider-smoke-${Date.now()}`},body:JSON.stringify(payload),signal:AbortSignal.timeout(25000)});
  const text=await r.text();let j:any;try{j=JSON.parse(text);}catch{throw new Error(`asset-service non-JSON HTTP ${r.status}: ${text.slice(0,500)}`);}if(r.status!==200&&r.status!==503)throw new Error(`asset-service HTTP ${r.status}: ${text.slice(0,1000)}`);return j;
}

async function authenticateGitHub(req:Request){
  const token=(req.headers.get("authorization")??"").replace(/^Bearer\s+/i,"").trim();if(!token)throw new Error("missing bearer token");
  const parts=token.split(".");if(parts.length!==3)throw new Error("invalid JWT");
  const header=JSON.parse(new TextDecoder().decode(b64url(parts[0]))),claims=JSON.parse(new TextDecoder().decode(b64url(parts[1])));
  if(header.alg!=="RS256"||!header.kid)throw new Error("unsupported OIDC signing header");
  if(claims.iss!==OIDC_ISSUER)throw new Error("OIDC issuer mismatch");
  const aud=Array.isArray(claims.aud)?claims.aud:[claims.aud];if(!aud.includes(OIDC_AUDIENCE))throw new Error("OIDC audience mismatch");
  const now=Math.floor(Date.now()/1000);if(Number(claims.exp)<=now||Number(claims.nbf??0)>now+30)throw new Error("OIDC token outside validity window");
  if(claims.repository!==REPOSITORY||String(claims.repository_id)!==REPOSITORY_ID||claims.ref!==REF||!ALLOWED_WORKFLOW_REFS.has(String(claims.workflow_ref)))throw new Error("OIDC repository/workflow scope mismatch");
  if(claims.runner_environment!=="github-hosted")throw new Error("GitHub-hosted runner required");
  const keys=await getJwks();const jwk=keys.find((x:any)=>x.kid===header.kid&&x.kty==="RSA");if(!jwk)throw new Error("OIDC signing key not found");
  const key=await crypto.subtle.importKey("jwk",jwk,{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["verify"]);
  const ok=await crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,b64url(parts[2]),new TextEncoder().encode(`${parts[0]}.${parts[1]}`));if(!ok)throw new Error("OIDC signature invalid");return claims;
}
async function getJwks(){if(jwksCache&&jwksCache.expires>Date.now())return jwksCache.keys;const r=await fetch(OIDC_JWKS,{headers:{Accept:"application/json"},signal:AbortSignal.timeout(10000)});if(!r.ok)throw new Error(`OIDC JWKS fetch ${r.status}`);const j=await r.json();if(!Array.isArray(j?.keys))throw new Error("OIDC JWKS malformed");jwksCache={expires:Date.now()+3600000,keys:j.keys};return j.keys;}
function b64url(v:string){const s=v.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(v.length/4)*4,"=");return Uint8Array.from(atob(s),c=>c.charCodeAt(0));}
function respond(v:any,status=200){return new Response(JSON.stringify(v),{status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"}});}
