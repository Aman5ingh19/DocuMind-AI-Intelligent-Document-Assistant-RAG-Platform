FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["src/DocumentAssistant.Api/DocumentAssistant.Api.csproj", "DocumentAssistant.Api/"]
RUN dotnet restore "DocumentAssistant.Api/DocumentAssistant.Api.csproj"

COPY src/DocumentAssistant.Api/ DocumentAssistant.Api/
WORKDIR "/src/DocumentAssistant.Api"
RUN dotnet build "DocumentAssistant.Api.csproj" -c Release -o /app/build
RUN dotnet publish "DocumentAssistant.Api.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080
ENV ASPNETCORE_ENVIRONMENT=Production

COPY --from=build /app/publish .
ENTRYPOINT ["dotnet", "DocumentAssistant.Api.dll"]
