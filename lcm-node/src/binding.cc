#include <napi.h>

#include <iostream>
#include <lcm/lcm-cpp.hpp>
#include <memory>

// ----------------------------------------------------------------------------
#define TRACE(IT) std::cout << __func__ << "::" << __LINE__ << "\t" << IT << std::endl;

// ----------------------------------------------------------------------------
class InstanceHandleWorker : public Napi::AsyncWorker {
  public:
    InstanceHandleWorker(const Napi::Env &env, lcm::LCM &lcm)
        : Napi::AsyncWorker{env, "InstanceHandleWorker"}, m_deferred{env}, lcm{lcm}
    {
    }

    /**
     * GetPromise associated with _deferred for return to JS
     */
    Napi::Promise GetPromise() { return m_deferred.Promise(); }

  protected:
    /**
     * Simulate heavy math work
     */
    void Execute() { this->lcm.handle(); }

    /**
     * Resolve the promise with the result
     */
    void OnOK() { m_deferred.Resolve(this->Env().Undefined()); }

    /**
     * Reject the promise with errors
     */
    void OnError(const Napi::Error &err) { m_deferred.Reject(err.Value()); }

  private:
    Napi::Promise::Deferred m_deferred;
    lcm::LCM &lcm;
};
// ----------------------------------------------------------------------------

class MyObject : public Napi::ObjectWrap<MyObject> {
  public:
    static Napi::Object Init(Napi::Env env, Napi::Object exports);
    MyObject(const Napi::CallbackInfo &info);

  private:
    Napi::Value GetValue(const Napi::CallbackInfo &info);
    Napi::Value PlusOne(const Napi::CallbackInfo &info);
    Napi::Value Multiply(const Napi::CallbackInfo &info);

    Napi::Value handle(const Napi::CallbackInfo &info)
    {
        Napi::Env env = info.Env();
        // Does Node take ownership of the pointer somehow? The example does not explain the
        // lifetime.
        auto worker = new InstanceHandleWorker(env, *this->_lcm);
        worker->Queue();
        return worker->GetPromise();
    }

    double value_;
    std::unique_ptr<lcm::LCM> _lcm;
};

Napi::Object MyObject::Init(Napi::Env env, Napi::Object exports)
{
    Napi::Function func = DefineClass(env, "MyObject",
                                      {
                                          InstanceMethod("plusOne", &MyObject::PlusOne),
                                          InstanceMethod("value", &MyObject::GetValue),
                                          InstanceMethod("handle", &MyObject::handle),
                                          //  InstanceMethod("multiply", &MyObject::Multiply)
                                      });

    Napi::FunctionReference *constructor = new Napi::FunctionReference();
    *constructor = Napi::Persistent(func);
    env.SetInstanceData(constructor);

    exports.Set("MyObject", func);
    return exports;
}

void onMsg(const lcm::ReceiveBuffer *rbuf, const std::string &channel, void *)
{
    std::cout << channel << std::endl;
}

class MyMessageHandler {
  public:
    void onMessage(const lcm::ReceiveBuffer *rbuf, const std::string &channel)
    {
        // do something with the message.  Raw message bytes are
        // accessible via rbuf->data
        std::cout << channel << std::endl;
    }
};

MyObject::MyObject(const Napi::CallbackInfo &info) : Napi::ObjectWrap<MyObject>(info)
{
    Napi::Env env = info.Env();

    int length = info.Length();

    if (length <= 0 || !info[0].IsNumber()) {
        Napi::TypeError::New(env, "Number expected").ThrowAsJavaScriptException();
        return;
    }

    Napi::Number value = info[0].As<Napi::Number>();
    this->value_ = value.DoubleValue();

    this->_lcm = std::make_unique<lcm::LCM>();
    auto handler = new MyMessageHandler;  // XXX LEAK for proof of concept
    _lcm->subscribe(".*", &MyMessageHandler::onMessage, handler);

    // std::cout << "Good lcm?" << this->_lcm->good() << std::endl;
    TRACE("");
}

Napi::Value MyObject::GetValue(const Napi::CallbackInfo &info)
{
    double num = this->value_;

    return Napi::Number::New(info.Env(), num);
}

Napi::Value MyObject::PlusOne(const Napi::CallbackInfo &info)
{
    this->value_ = this->value_ + 1;

    return MyObject::GetValue(info);
}

// Napi::Value MyObject::Multiply(const Napi::CallbackInfo &info)
// {
//     Napi::Number multiple;
//     if (info.Length() <= 0 || !info[0].IsNumber()) {
//         multiple = Napi::Number::New(info.Env(), 1);
//     } else {
//         multiple = info[0].As<Napi::Number>();
//     }

//     // Napi::Object obj = info.Env().GetInstanceData<Napi::FunctionReference>()->New(
//     //     {Napi::Number::New(info.Env(), this->value_ * multiple.DoubleValue())});

//     return *this;
// }

Napi::Object InitAll(Napi::Env env, Napi::Object exports)
{
    return MyObject::Init(env, exports);
}

NODE_API_MODULE(addon, InitAll)