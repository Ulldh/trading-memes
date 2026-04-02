import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"
import Stripe from "https://esm.sh/stripe@14?target=deno"

const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY')!, {
  apiVersion: '2023-10-16',
  httpClient: Stripe.createFetchHttpClient(),
})

const supabaseUrl = Deno.env.get('SUPABASE_URL')!
const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
const webhookSecret = Deno.env.get('STRIPE_WEBHOOK_SECRET')!

serve(async (req) => {
  const signature = req.headers.get('Stripe-Signature')
  if (!signature) {
    console.error('Missing Stripe-Signature header')
    return new Response(JSON.stringify({ error: 'Missing signature' }), { status: 400 })
  }

  const body = await req.text()

  let event: Stripe.Event
  try {
    event = await stripe.webhooks.constructEventAsync(body, signature, webhookSecret)
  } catch (err) {
    console.error('Signature verification failed:', (err as Error).message)
    return new Response(JSON.stringify({ error: 'Invalid signature' }), { status: 400 })
  }

  console.log(`Webhook received: ${event.type} (${event.id})`)

  const supabase = createClient(supabaseUrl, supabaseServiceKey)

  try {
    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object as Stripe.Checkout.Session
        const email = session.customer_email || session.customer_details?.email
        const customerId = session.customer as string
        const subscriptionId = session.subscription as string
        const userId = session.client_reference_id

        console.log(`checkout.session.completed: email=${email}, customerId=${customerId}, subscriptionId=${subscriptionId}, userId=${userId}`)

        if (!subscriptionId) {
          console.error('No subscription ID in session')
          return new Response(JSON.stringify({ error: 'No subscription in session' }), { status: 400 })
        }

        let sub: Stripe.Subscription
        try {
          sub = await stripe.subscriptions.retrieve(subscriptionId)
        } catch (err) {
          console.error('Failed to retrieve subscription:', (err as Error).message)
          return new Response(JSON.stringify({ error: 'Failed to retrieve subscription', detail: (err as Error).message }), { status: 500 })
        }

        const priceId = sub.items.data[0]?.price.id
        const plan = priceId === Deno.env.get('STRIPE_PRICE_ID_ENTERPRISE') ? 'enterprise' : 'pro'
        const maxTokens = plan === 'enterprise' ? 999 : 10

        console.log(`Plan: ${plan} (priceId=${priceId})`)

        const updatePayload = {
          role: plan,
          subscription_status: 'active',
          subscription_plan: plan,
          stripe_customer_id: customerId,
          subscription_end: new Date(sub.current_period_end * 1000).toISOString(),
          max_watchlist_tokens: maxTokens,
          updated_at: new Date().toISOString(),
        }

        // Buscar perfil por user_id (client_reference_id) primero, fallback a email
        let query
        if (userId) {
          console.log(`Matching profile by user_id: ${userId}`)
          query = supabase.from('profiles').update(updatePayload).eq('id', userId).select()
        } else if (email) {
          console.log(`Matching profile by email: ${email}`)
          query = supabase.from('profiles').update(updatePayload).eq('email', email).select()
        } else {
          console.error('No userId or email to match profile')
          return new Response(JSON.stringify({ error: 'No userId or email' }), { status: 400 })
        }

        const { data, error } = await query

        if (error) {
          console.error('DB update failed:', JSON.stringify(error))
          return new Response(JSON.stringify({ error: 'DB update failed', detail: error.message }), { status: 500 })
        }

        if (!data || data.length === 0) {
          console.error(`No profile found (userId=${userId}, email=${email})`)
          return new Response(JSON.stringify({ error: 'No profile found', userId, email }), { status: 404 })
        }

        console.log(`Profile updated: ${data[0].email} -> ${plan}`)
        break
      }

      case 'customer.subscription.updated': {
        const sub = event.data.object as Stripe.Subscription
        const customerId = sub.customer as string

        console.log(`subscription.updated: customerId=${customerId}, status=${sub.status}`)

        const { error } = await supabase.from('profiles').update({
          subscription_status: sub.status,
          subscription_end: new Date(sub.current_period_end * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        }).eq('stripe_customer_id', customerId)

        if (error) console.error('DB update failed:', JSON.stringify(error))
        break
      }

      case 'customer.subscription.deleted': {
        const sub = event.data.object as Stripe.Subscription
        const customerId = sub.customer as string

        console.log(`subscription.deleted: customerId=${customerId}`)

        const { error } = await supabase.from('profiles').update({
          role: 'free',
          subscription_status: 'cancelled',
          subscription_plan: 'free',
          max_watchlist_tokens: 3,
          updated_at: new Date().toISOString(),
        }).eq('stripe_customer_id', customerId)

        if (error) console.error('DB update failed:', JSON.stringify(error))
        break
      }

      case 'invoice.payment_failed': {
        const invoice = event.data.object as Stripe.Invoice
        const customerId = invoice.customer as string

        console.log(`payment_failed: customerId=${customerId}`)

        const { error } = await supabase.from('profiles').update({
          subscription_status: 'past_due',
          updated_at: new Date().toISOString(),
        }).eq('stripe_customer_id', customerId)

        if (error) console.error('DB update failed:', JSON.stringify(error))
        break
      }

      default:
        console.log(`Unhandled event: ${event.type}`)
    }
  } catch (err) {
    console.error(`Error processing ${event.type}:`, (err as Error).message)
    return new Response(JSON.stringify({ error: 'Internal error', detail: (err as Error).message }), { status: 500 })
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { 'Content-Type': 'application/json' },
    status: 200,
  })
})
