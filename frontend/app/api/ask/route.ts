export const maxDuration = 60;

export async function POST(req: Request) {
  const { question, conversation_id } = await req.json();
  const backendUrl = process.env.BACKEND_URL;
  const permissionKey = process.env.BACKEND_API_KEY;
  const incomingIP = req.headers.get("x-forwarded-for")?.split(",")[0].trim() ?? "unknown"

  if (!backendUrl) {
    return Response.json({ error: 'BACKEND_URL is not configured' }, { status: 500 });
  }

  if(!permissionKey){
    return Response.json({error: "Permission key is missing"},{status: 500});
  }

  try {
    const res = await fetch(`${backendUrl}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': permissionKey, 'X-Client-IP': incomingIP },
      body: JSON.stringify({ question, conversation_id }),
    });

    if (!res.ok) {
      const text = await res.text();
      return Response.json({ error: text || 'Backend returned an error' }, { status: res.status });
    }

    const data = await res.json();
    return Response.json(data);
  } catch {
    return Response.json({ error: 'Backend unreachable' }, { status: 502 });
  }
}
