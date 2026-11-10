#include "shared/interfaces/ApiDocumentation.h"
#include <drogon/drogon.h>

int main(int argc, char *argv[])
{
    drogon::app().setFileTypes({});
    mirage::http::registerApiDocumentation(std::filesystem::absolute(argv[0]).parent_path() /
                                           "docs");
    LOG_INFO << "Servidor IAM iniciando en http://localhost:8080";

    drogon::app().registerHandler(
        "/health",
        [](const drogon::HttpRequestPtr &,
           std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
            auto response = drogon::HttpResponse::newHttpResponse();
            response->setContentTypeCode(drogon::CT_TEXT_PLAIN);
            response->setBody("ok");
            callback(response);
        },
        {drogon::Get});

    // Configurar puerto de escucha
    drogon::app().addListener("0.0.0.0", 8080);

    // Iniciar el motor asíncrono
    drogon::app().run();

    return 0;
}
