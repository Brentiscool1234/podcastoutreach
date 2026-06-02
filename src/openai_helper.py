from openai import OpenAI


def _client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def generate_pitch(api_key: str, business: dict) -> str:
    client = _client(api_key)
    system = (
        "You are a podcast booking expert. Write compelling, personalized podcast guest pitch emails. "
        "The pitch should be professional, concise (under 250 words), and clearly articulate the value "
        "the guest brings to the host's audience. Do NOT use generic fluff. Be specific and genuine."
    )
    user = (
        f"Write a podcast guest pitch email for the following person/business:\n\n"
        f"Company/Name: {business.get('company_name', '')}\n"
        f"Website: {business.get('website', '')}\n"
        f"Description: {business.get('description', '')}\n"
        f"Target Audience: {business.get('target_audience', '')}\n"
        f"Value Proposition: {business.get('value_proposition', '')}\n"
        f"Host/Sender Name: {business.get('host_name', '')}\n\n"
        "Write a compelling pitch email that includes: a strong opening, why they'd be a great guest, "
        "specific value for the podcast's audience, 2-3 potential topic ideas, and a clear call to action."
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.7,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


def refine_pitch(api_key: str, current_pitch: str, instructions: str) -> str:
    client = _client(api_key)
    system = (
        "You are a podcast booking expert. Refine podcast guest pitch emails based on specific instructions. "
        "Preserve the core message and information unless asked to change it. Return only the refined pitch."
    )
    user = (
        f"Here is a podcast pitch:\n\n{current_pitch}\n\n"
        f"Please refine it according to these instructions: {instructions}\n\n"
        "Return only the refined pitch text."
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.7,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()
