export const maxDuration = 60;

export async function POST(req: Request) {
  const { question, conversation_id } = await req.json();
  const backendUrl = process.env.BACKEND_URL;

  if (!backendUrl) {
    return Response.json({ error: 'BACKEND_URL is not configured' }, { status: 500 });
  }

  try {
    const res = await fetch(`${backendUrl}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
